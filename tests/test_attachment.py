import os
import httpx
import sys

VIKUNJA_API_TOKEN = os.getenv("VIKUNJA_API_TOKEN")
VIKUNJA_BASE_URL = os.getenv("VIKUNJA_BASE_URL", "https://tracker.bestfam.us/api/v1")
TEST_TASK_ID = "78"

def test_upload(method):
    print(f"Testing attachment upload with {method}...")
    url = f"{VIKUNJA_BASE_URL}/tasks/{TEST_TASK_ID}/attachments"
    headers = {"Authorization": f"Bearer {VIKUNJA_API_TOKEN}"}
    
    dummy_file = "test_attachment.txt"
    with open(dummy_file, "w") as f:
        f.write(f"Test attachment content via {method}")
    
    try:
        with open(dummy_file, "rb") as f:
            files = {"files": (dummy_file, f)}
            with httpx.Client() as client:
                if method == "PUT":
                    response = client.put(url, headers=headers, files=files)
                else:
                    response = client.post(url, headers=headers, files=files)
                
                print(f"Status Code: {response.status_code}")
                print(f"Response: {response.text}")
                return response.status_code == 201 or response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        if os.path.exists(dummy_file):
            os.remove(dummy_file)

if __name__ == "__main__":
    if not VIKUNJA_API_TOKEN:
        print("Error: VIKUNJA_API_TOKEN not set")
        sys.exit(1)
        
    success_put = test_upload("PUT")
    print("-" * 20)
    success_post = test_upload("POST")
    
    if success_put:
        print("\n✅ PUT method worked!")
    if success_post:
        print("\n✅ POST method worked!")
    if not success_put and not success_post:
        print("\n❌ Neither method worked.")
