
# PDF Renamer Script

This script created with ChatGPT renames PDF files based on their content by generating creative titles using the OpenAI API. The script can extract text snippets from PDFs, send these snippets to the OpenAI API to create a relevant and creative title, and rename the PDF files accordingly.
Prerequisites

Before using the script, make sure you have the following installed:

    Python 3.x
    openai Python library
    nltk Python library
    pdfminer.six Python library
    PyMuPDF Python library (imported as fitz)
    argparse, glob, json, logging, os, re (these are usually part of the Python standard library)

To install the required libraries, run:

```bash
pip install openai nltk pdfminer.six PyMuPDF
```
# Setup

    API Key: Place your OpenAI API key in a .secret file in the script directory in the following format:

```json

{
    "openai_api_key": "your_openai_api_key_here"
}
```
# Usage

Run the script using the command line with the following options:

```bash

python rename_pdfs.py [OPTIONS] "PDFS/*.pdf"
```
# Command Line Options
    file_pattern: (required) The path or file pattern to specify which PDF files to process. Wildcards are allowed (e.g., "PDFS/*.pdf").

    --num_sentences: Number of sentences to extract from the beginning of each PDF to generate a title. This option is mutually exclusive with --num_words.

    --num_words: Number of words to extract from the beginning of each page of the PDF to generate a title. This option is mutually exclusive with --num_sentences.

    --system_prompt: (optional) A base prompt to set the context for the OpenAI model. Default: "You are a helpful assistant. Use the information below to create a creative title.".

    --additional_prompt: (optional) Additional text to customize the prompt when generating the title. For example: "If the content is full of recipes, generate a name like 'Compilation of Oriental Recipes'".

    --max_tokens: (optional) Maximum number of tokens for the OpenAI model to generate the title. Default: 50.

    --dry_mode: (optional) If set, the script will not actually rename files but will log what it would do. Useful for testing.

# Example Usage
```bash
python rename_pdfs.py --num_words 20 "PDFS/*.pdf" --additional_prompt "If the content is full of recipes, generate a name like 'Compilation of Oriental Recipes'"
```
This example will:

    Extract the first 20 words from each PDF in the specified directory.
    Use OpenAI to generate a creative title.
    If the content appears to be recipes, it will suggest names like 'Compilation of Oriental Recipes'.
    Rename the PDFs based on the generated titles.

# Logging
The script logs various activities, such as the file being processed, any errors encountered, and the renaming actions. By default, logging information is output to the console.

#Notes
The script attempts to use pdfminer.six for text extraction. If it fails, it falls back to using PyMuPDF.
Invalid characters in filenames (e.g., < > : " / \ | ? * -) are replaced with - to ensure compatibility across different operating systems.
The script handles cases where files cannot be renamed due to extraction errors by skipping them and logging a warning.#
