#!/bin/bash
# Best-quality PDF for Google Drive: uses Chrome headless to print HTML.
# Usage: ./scripts/print_pdf_chrome.sh [html_file] [output_pdf]

set -euo pipefail
HTML="${1:-$HOME/Downloads/PAHS_完整学习包_Zachary_Zhou.html}"
PDF="${2:-$HOME/Downloads/PAHS_完整学习包_Zachary_Zhou_chrome.pdf}"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

if [[ ! -f "$HTML" ]]; then
  echo "HTML not found: $HTML"
  echo "Run first: cd ~/Desktop/PAHS && python3 scripts/md_to_pdf.py"
  exit 1
fi

"$CHROME" --headless=new --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="$PDF" "file://$HTML"
echo "Wrote $PDF"
