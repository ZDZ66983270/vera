
# Script to fix indentation in app.py
file_path = "/Users/zhangzy/My Docs/Privates/22-AI编程/VERA/app.py"

with open(file_path, "r") as f:
    lines = f.readlines()

new_lines = []
target_start = 802 # 0-indexed, corresponding to line 803
target_end = 1010  # Cover until end

for i, line in enumerate(lines):
    # Only process lines from 803 onwards (index 802)
    if i >= target_start:
        # If line starts with 16 spaces, reduce to 12
        if line.startswith("                "):
            new_lines.append(line[4:])
        # If line starts with 12 spaces (the except block), reduce to 8
        elif line.startswith("            "):
             new_lines.append(line[4:])
        # Empty lines or other indentation? Check carefully
        elif line.strip() == "":
            new_lines.append(line)
        else:
            # If it's less indented than expected, keep it (might be end of file)
            new_lines.append(line)
    else:
        new_lines.append(line)

with open(file_path, "w") as f:
    f.writelines(new_lines)

print("Indentation fixed.")
