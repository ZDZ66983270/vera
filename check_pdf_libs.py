try:
    import pdfplumber
    print("pdfplumber available")
except ImportError:
    print("pdfplumber NOT available")

try:
    import pypdf
    print("pypdf available")
except ImportError:
    print("pypdf NOT available")
