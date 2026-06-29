#!/bin/bash
# Runs automatically on Streamlit Community Cloud before the app starts.
# Downloads the spaCy English model required by preprocessing.py.
python -m spacy download en_core_web_sm
