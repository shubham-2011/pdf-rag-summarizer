import re

sample_header = "1. Shubham Kumar Mobile: +91-7322007327 Email: shubhammishra000@gmail.com GitHub: https://github.com/shubham200020 LinkedIn: https://linkedin.com/in/shubham-kumar-48b57023b CAREER OBJECTIVE: Software Engineer"

def extract_contact_info(text):
    phone_match = re.search(r'(?:mobile|phone|tel|cell)?[:\s]*(\+?\d[\d\s\-\(\)]{8,16}\d)', text, re.I)
    email_match = re.search(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', text)
    github_match = re.search(r'(https?://(?:www\.)?github\.com/[a-zA-Z0-9_-]+)', text, re.I)
    linkedin_match = re.search(r'(https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+)', text, re.I)
    
    return {
        "phone": phone_match.group(1).strip() if phone_match else None,
        "email": email_match.group(1).strip() if email_match else None,
        "github": github_match.group(1).strip() if github_match else None,
        "linkedin": linkedin_match.group(1).strip() if linkedin_match else None,
    }

print("Contact Extraction:", extract_contact_info(sample_header))
