import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    response = requests.get("https://lms.lilit.lk/about", verify=False, timeout=10)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Remove navigation, headers, footers
    for tag in soup(['nav', 'header', 'footer', 'aside', 'script', 'style']):
        tag.decompose()
    
    content = soup.get_text(separator='\n', strip=True)
    
    # Save full content to file
    with open("about_page_content.txt", "w", encoding="utf-8") as f:
        f.write(content)
    
    print("Saved about_page_content.txt")
    print(f"\nTotal characters: {len(content)}")
    print("\n--- First 2000 characters ---")
    print(content[:2000])
    
except Exception as e:
    print(f"Error: {e}")
