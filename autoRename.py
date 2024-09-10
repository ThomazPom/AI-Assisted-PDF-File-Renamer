import os
import argparse
import glob
import json
import time
from openai import OpenAI
import logging
from nltk.tokenize import sent_tokenize
from pdfminer.high_level import extract_text
from pdfminer.layout import LAParams
import fitz  # PyMuPDF
import re
from tqdm import tqdm as tdqm

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


def extract_text_snippet(file_path, num_sentences=1, num_words=None):
    try:
        # Attempt to use pdfminer.six to extract the text
        laparams = LAParams()
        text = extract_text(file_path, laparams=laparams)
        pages = text.split('\x0c')  # Split the text into pages
        snippets = [get_text_snippet(page, num_sentences, num_words) for page in pages]
    except Exception as e:
        print(f"pdfminer.six failed with error: {e}. Falling back to PyMuPDF.")
        snippets = extract_with_pymupdf(file_path, num_sentences, num_words)

    return snippets


def get_text_snippet(text, num_sentences, num_words):
    if num_words is not None:
        words = re.findall(r'\w+', text)  # Extract words using regex
        return ' '.join(words[:num_words])
    else:
        sentences = sent_tokenize(text)
        return ' '.join(sentences[:num_sentences])


def extract_with_pymupdf(file_path, num_sentences, num_words):
    snippets = []
    try:
        with fitz.open(file_path) as doc:
            for page in doc:
                text = page.get_text()
                snippets.append(get_text_snippet(text, num_sentences, num_words))
    except Exception as e:
        print(f"Failed to extract text using PyMuPDF: {e}")

    return snippets


def generate_creative_title(content, system_prompt, additional_prompt, max_tokens, model="gpt-4o-mini"):
    """
    Uses OpenAI to generate a creative title based on the extracted content.
    """
    full_system_prompt = system_prompt
    if additional_prompt:
        full_system_prompt += f" Additional instructions: {additional_prompt}"

    user_content = f"Extracted content:\n{content}"

    # Log the system prompt and user content before sending to OpenAI
    logging.debug(f"System prompt: {full_system_prompt}")
    logging.debug(f"User content being sent to OpenAI: {user_content}")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": full_system_prompt},
            {"role": "user", "content": user_content}
        ],
        max_tokens=max_tokens  # Use configurable max_tokens value
    )
    title = response.choices[0].message.content.strip()
    return title


def sanitize_filename(filename):
    """
    Remove or replace characters that are not allowed in Windows file names.
    """

    invalid_chars = '<>:"/\\|?*-\n'
    for char in invalid_chars:
        filename = filename.replace(char, ' - ')
    filename = filename.strip(" -._")
    return filename.replace('  ', ' ').replace('  ', ' ').replace('  ', ' ')


def rename_pdf(file_path, new_title, dry_mode):
    """
    Renames the PDF file using the provided new title.
    If dry_mode is True, only log the renaming action without performing it.
    """
    directory, original_filename = os.path.split(file_path)
    sanitized_title = sanitize_filename(new_title)  # Sanitize the title
    new_filename = f"{sanitized_title}.pdf"
    new_file_path = os.path.join(directory, new_filename)

    if dry_mode:
        logging.info(f"[DRY MODE] Would rename file {original_filename} to {new_filename}")
    else:
        try:
            os.rename(file_path, new_file_path)
            logging.info(f"File @ {original_filename} renamed to  \n ####{" " * 10} {new_filename}")
        except FileExistsError as e:
            logging.error(f"Failed to rename file {original_filename} to {new_filename}: {e}")

            while True:
                todo = input(
                    "Enter 'r' to rename, 's' to skip, 'q' to quit, 'o' to open both files, d to delete current file, e to erase the existent file: ")
                if todo == "r":
                    new_filename = input("Enter new name: ")
                    new_file_path = os.path.join(directory, new_filename)
                    os.rename(file_path, new_file_path)
                    logging.info(f"File @ {original_filename} renamed to  \n ####{" " * 10} {new_filename}")
                    break
                elif todo == "s":
                    break
                elif todo == "e":
                    # erase the file
                    os.remove(new_file_path)
                    os.rename(file_path, new_file_path)
                    break
                elif todo == "d":
                    # delete the  file
                    os.remove(file_path)
                    break
                elif todo == "q":
                    exit()
                elif todo == "o":
                    # open both file with default application
                    os.startfile(new_file_path)
                    os.startfile(file_path)


def process_pdfs(file_pattern, num_sentences, num_words, system_prompt, additional_prompt, max_tokens, dry_mode, sleep,
                 model):
    """
    Processes all PDF files matching the specified file pattern.
    """
    for file_path in tdqm(glob.glob(file_pattern), "PDFs processing"):
        if file_path.endswith(".pdf"):
            logging.info(f"Processing file: {file_path}")
            if num_words:
                snippet = extract_text_snippet(file_path, num_sentences=None, num_words=num_words)
            else:
                snippet = extract_text_snippet(file_path, num_sentences=num_sentences)

            if snippet:
                creative_title = generate_creative_title(snippet, system_prompt, additional_prompt, max_tokens, model)
                rename_pdf(file_path, creative_title, dry_mode)

            else:
                logging.warning(f"Skipping file {file_path} due to extraction errors.")

            time.sleep(sleep)  # Sleep for 3 second to avoid rate limiting


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Renames PDF files based on their content.")
    parser.add_argument("file_pattern", type=str,
                        help="Path or file pattern for the PDF files to be processed (may include wildcards)")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--num_sentences", type=int, default=1,
                       help="Number of sentences to extract from the beginning of each PDF to generate a title")
    group.add_argument("--num_words", type=int,
                       help="Number of words to extract from the beginning of each page of the PDF to generate a title")

    parser.add_argument("--system_prompt", type=str,
                        default="You are a helpful assistant. Use the information below to create a creative title.",
                        help="The base system prompt to set the context for the OpenAI model")

    parser.add_argument("--additional_prompt", type=str, default="",
                        help="Additional text to customize the prompt when generating the title")

    parser.add_argument("--max_tokens", type=int, default=50,
                        help="Maximum number of tokens for the OpenAI model to generate the title")

    parser.add_argument("--dry_mode", action="store_true",
                        help="If set, the script will not actually rename files but will log what it would do")

    parser.add_argument("--sleep", type=int, default=3, help="Time to sleep between each file to avoid rate limiting")

    parser.add_argument("--model", type=str, default="gpt-4o-mini", help="OpenAI model to use")
    args = parser.parse_args()

    process_pdfs(args.file_pattern, args.num_sentences, args.num_words, args.system_prompt, args.additional_prompt,
                 args.max_tokens, args.dry_mode, args.sleep, args.model)
