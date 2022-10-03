mkdir -p ~/.streamlit/

echo "[theme]
primaryColor='#d96098'
backgroundColor='#ffffff'
secondaryBackgroundColor='#faeee7'
textColor='#325288'
font='sans serif'
[server]\n\
port = $PORT\n\
enableCORS = false\n\
headless = true\n\
\n\
" > ~/.streamlit/config.toml
