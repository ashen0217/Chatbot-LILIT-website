import requests
from bs4 import BeautifulSoup
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_all_courses_structured():
    """Fetch all courses and extract structured data dynamically"""
    try:
        # Fetch main courses page
        response = requests.get("https://lms.lilit.lk/all-courses", verify=False)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all course links/cards
        # Try multiple selectors (common LMS patterns)
        courses = []

        # Look for course links - usually in hrefs containing /course-details/
        all_links = soup.find_all('a', href=True)
        course_ids = set()

        for link in all_links:
            href = link.get('href', '')
            if '/course-details/' in href:
                # Extract course ID
                try:
                    course_id = href.split('/course-details/')[-1].strip('/')
                    if course_id.isdigit():
                        course_ids.add(int(course_id))
                except:
                    pass

        # Now fetch details for each course ID
        for course_id in sorted(course_ids):
            course_data = fetch_course_details(course_id)
            if course_data:
                courses.append(course_data)

        return courses

    except Exception as e:
        print(f"Error: {e}")
        return []

def fetch_course_details(course_id):
    """Fetch and parse a single course's details"""
    try:
        url = f"https://lms.lilit.lk/course-details/{course_id}"
        response = requests.get(url, verify=False, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove script/style tags
        for tag in soup(['script', 'style', 'nav', 'header', 'footer']):
            tag.decompose()

        text = soup.get_text(separator=' ', strip=True)

        # Extract key information
        course_data = {
            'id': course_id,
            'url': url,
            'raw_content': text
        }

        # Basic extraction patterns
        if 'duration' in text.lower():
            # Try to find duration pattern (e.g., "2 months", "4 days", "6 months")
            import re
            duration_match = re.search(r'(\d+)\s*(days?|weeks?|months?)', text, re.IGNORECASE)
            if duration_match:
                course_data['duration'] = duration_match.group(0)

        if 'lkr' in text.lower():
            # Try to find LKR amount
            import re
            fee_match = re.search(r'(?:LKR|Rs\.?)\s*([\d,]+)', text, re.IGNORECASE)
            if fee_match:
                course_data['fee'] = f"LKR {fee_match.group(1)}"

        return course_data

    except Exception as e:
        print(f"Error fetching course {course_id}: {e}")
        return None

if __name__ == "__main__":
    courses = fetch_all_courses_structured()
    print(json.dumps(courses, indent=2))
