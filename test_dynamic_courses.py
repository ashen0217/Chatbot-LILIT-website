"""Test script to verify dynamic course fetching implementation"""
import asyncio
import re
import urllib3
from bs4 import BeautifulSoup
import httpx

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class CachedData:
    def __init__(self, ttl_seconds=300):
        self.cache = {}
        self.ttl = ttl_seconds
        import time
        self.time = time

    def get(self, key):
        if key in self.cache:
            data, timestamp = self.cache[key]
            if self.time.time() - timestamp < self.ttl:
                return data
            del self.cache[key]
        return None

    def set(self, key, value):
        self.cache[key] = (value, self.time.time())


cache = CachedData(ttl_seconds=3600)


async def get_all_course_details():
    """Fetch live course data dynamically from LMS website with 60-minute cache"""
    cache_key = "all_courses_data"
    cached = cache.get(cache_key)

    if cached is not None:
        print("✓ Using cached course data")
        return cached

    print("⏳ Fetching live course data from LMS...")

    try:
        # Fetch all courses dynamically from the LMS website
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get("https://lms.lilit.lk/all-courses", timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find all course links/cards
            all_links = soup.find_all('a', href=True)
            course_ids = set()

            for link in all_links:
                href = link.get('href', '')
                if '/course-details/' in href:
                    try:
                        course_id = href.split('/course-details/')[-1].strip('/')
                        if course_id.isdigit():
                            course_ids.add(int(course_id))
                    except:
                        pass

            print(f"✓ Found {len(course_ids)} courses: {sorted(course_ids)}")

            # Fetch details for each course ID
            formatted_courses = []
            for course_id in sorted(course_ids):
                try:
                    course_response = await client.get(
                        f"https://lms.lilit.lk/course-details/{course_id}", 
                        timeout=10
                    )
                    course_soup = BeautifulSoup(course_response.text, 'html.parser')

                    # Remove script/style tags
                    for tag in course_soup(['script', 'style', 'nav', 'header', 'footer']):
                        tag.decompose()

                    text = course_soup.get_text(separator=' ', strip=True)

                    # Extract structured data
                    course_name = f"Course ID: {course_id}"
                    duration = "Not specified"
                    fee = "Not specified"

                    # Try to find duration pattern
                    duration_match = re.search(r'(\d+)\s*(days?|weeks?|months?)', text, re.IGNORECASE)
                    if duration_match:
                        duration = duration_match.group(0)

                    # Try to find LKR fee
                    fee_match = re.search(r'(?:LKR|Rs\.?)\s*([\d,]+)', text, re.IGNORECASE)
                    if fee_match:
                        fee = f"LKR {fee_match.group(1)}"

                    formatted_courses.append(f"""=== COURSE ID: {course_id} ===
Duration: {duration}
Fee: {fee}
""")
                    print(f"  ✓ Course {course_id}: {duration}, {fee}")
                except Exception as e:
                    print(f"  ⚠ Error fetching course {course_id}: {e}")
                    continue

            if formatted_courses:
                course_text = "\n".join(formatted_courses)
            else:
                course_text = "No courses found (using fallback)"

            # Cache for 60 minutes
            cache.set(cache_key, course_text)
            print(f"✓ Cached course data (60 minutes TTL)")
            return course_text

    except Exception as e:
        print(f"✗ Error fetching live courses: {e}")
        return "Error fetching courses"


async def main():
    print("=" * 60)
    print("TESTING DYNAMIC COURSE FETCHING")
    print("=" * 60)
    
    # First call - should fetch
    print("\n[Test 1] First call (should fetch from LMS):")
    result1 = await get_all_course_details()
    print(f"\nResult length: {len(result1)} characters")
    
    # Second call - should use cache
    print("\n[Test 2] Second call (should use cache):")
    result2 = await get_all_course_details()
    print(f"Result length: {len(result2)} characters")
    
    # Verify results match
    if result1 == result2:
        print("✓ Cache working correctly!")
    else:
        print("⚠ Results differ (expected if cache expired)")
    
    # Show sample output
    print("\n" + "=" * 60)
    print("SAMPLE COURSE DATA:")
    print("=" * 60)
    lines = result1.split('\n')[:20]
    for line in lines:
        print(line)
    
    print("\n✅ Dynamic course fetching test complete!")


if __name__ == "__main__":
    asyncio.run(main())
