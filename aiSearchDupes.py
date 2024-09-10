import os
import argparse
import glob
import json
import time
import logging
from pdfminer.high_level import extract_text
import fitz  # PyMuPDF
import re
from tqdm import tqdm as tdqm
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# Load API key from a .secret file
def load_api_key(api_key_path):
    with open(api_key_path, 'r') as secret_file:
        secrets = json.load(secret_file)
        return secrets['openai_api_key']


# Initialize OpenAI client
script_dir = os.path.dirname(os.path.realpath(__file__))
api_key = load_api_key(os.path.join(script_dir, ".secret"))  # Replace with your API key
client = OpenAI(api_key=api_key)


def extract_with_pymupdf(file_path, num_sentences, num_words):
    """
    Extracts text from the first page using PyMuPDF for faster performance.
    """
    snippets = []
    try:
        with fitz.open(file_path) as doc:
            text = doc[0].get_text()  # Get text from the first page
            snippets.append(get_text_snippet(text, num_sentences, num_words))
    except Exception as e:
        logging.error(f"Failed to extract text from {file_path} using PyMuPDF: {e}")
    return snippets


def get_text_snippet(text, num_sentences, num_words):
    if num_words is not None:
        words = re.findall(r'\w+', text)  # Extract words using regex
        return ' '.join(words[:num_words])
    else:
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        return ' '.join(sentences[:num_sentences])


def check_duplicates_using_ai(pdf_snippets):
    """
    Use OpenAI to check for duplicates among multiple snippets.
    This sends all snippets together for a batch comparison and refers to filenames instead of snippet numbers.
    """
    comparison_prompt = "Here is a list of text snippets from different PDFs. Find any pairs that appear to be duplicates based on content:\n\n"

    # Use filenames in the prompt instead of snippet numbers
    for file, snippet in pdf_snippets.items():
        comparison_prompt += f"File '{os.path.basename(file)}': {snippet}\n"

    comparison_prompt += "\nPlease list which files are duplicates (e.g., 'File A and File B are duplicates')."

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system",
             "content": "You are a helpful assistant that identifies duplicate text content from PDFs."},
            {"role": "user", "content": comparison_prompt}
        ],
        max_tokens=1000
    )

    result = response.choices[0].message.content.strip()
    return result


def extract_and_store_snippet(file_path, num_sentences, num_words):
    """
    Extracts text snippet from the first page of the PDF and returns it.
    """
    return extract_with_pymupdf(file_path, num_sentences, num_words)


def delete_file(file_path):
    """
    Deletes the file at the given file path.
    """
    try:
        os.remove(file_path)
        logging.info(f"Deleted duplicate file: {file_path}")
    except OSError as e:
        logging.error(f"Error deleting file {file_path}: {e}")


def process_pdfs_for_duplicates(file_pattern, num_sentences, num_words, sleep, delete_dupes):
    """
    Processes all PDF files matching the specified file pattern and checks for duplicates.
    This version uses parallel processing to speed up the text extraction and includes an option to delete duplicates.
    """
    pdf_snippets = {}
    pdf_files = glob.glob(file_pattern)

    with ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(extract_and_store_snippet, file_path, num_sentences, num_words): file_path
            for file_path in pdf_files if file_path.endswith(".pdf")
        }

        for future in tdqm(futures, desc="Processing PDFs"):
            file_path = futures[future]
            try:
                snippet = future.result()
                if snippet:
                    pdf_snippets[file_path] = snippet[0]  # Store the first snippet of the PDF
                else:
                    logging.warning(f"Skipping file {file_path} due to extraction errors.")
            except Exception as e:
                logging.error(f"Error processing file {file_path}: {e}")

    # Send all snippets to OpenAI in one request
    if pdf_snippets:
        duplicate_report = check_duplicates_using_ai(pdf_snippets)
        logging.info(f"Duplicate Report:\n{duplicate_report}")

        # Parse the duplicate report and delete files if requested
        if delete_dupes:
            # Example: Looking for 'File A and File B are duplicates' and deleting 'File B'
            lines = duplicate_report.split('\n')
            for line in lines:
                if 'are duplicates' in line:
                    # Extract filenames from the report (this logic depends on how the report is formatted)
                    try:
                        parts = line.split(" and ")
                        file1 = parts[0].split("File '")[1].rstrip("'")
                        file2 = parts[1].split("File '")[1].split(" ")[0].rstrip("'")

                        file1_path = next((path for path in pdf_snippets.keys() if os.path.basename(path) == file1),
                                          None)
                        file2_path = next((path for path in pdf_snippets.keys() if os.path.basename(path) == file2),
                                          None)

                        if file2_path and os.path.exists(file2_path):
                            delete_file(file2_path)  # Deleting file2 by default
                    except Exception as e:
                        logging.error(f"Error parsing duplicate report or deleting files: {e}")
    else:
        logging.warning("No valid snippets to process for duplicates.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Searches for duplicate PDFs based on their content and optionally deletes duplicates.")
    parser.add_argument("file_pattern", type=str,
                        help="Path or file pattern for the PDF files to be processed (may include wildcards)")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--num_sentences", type=int, default=1,
                       help="Number of sentences to extract from the beginning of each PDF to compare")
    group.add_argument("--num_words", type=int,
                       help="Number of words to extract from the beginning of each page of the PDF to compare")

    parser.add_argument("--delete_dupes", action="store_true",
                        help="If set, the script will delete duplicate files based on the comparison")

    parser.add_argument("--sleep", type=int, default=3, help="Time to sleep between each file to avoid rate limiting")

    args = parser.parse_args()

    process_pdfs_for_duplicates(args.file_pattern, args.num_sentences, args.num_words, args.sleep, args.delete_dupes)
