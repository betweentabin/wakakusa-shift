#!/usr/bin/env python3
import re

def find_missing_braces(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract only JavaScript content (between <script> tags)
    script_pattern = r'<script[^>]*>(.*?)</script>'
    scripts = re.findall(script_pattern, content, re.DOTALL)
    
    for i, script in enumerate(scripts):
        print(f"\n=== Script {i+1} ===")
        lines = script.split('\n')
        
        brace_stack = []
        paren_stack = []
        bracket_stack = []
        
        for line_num, line in enumerate(lines, 1):
            # Skip template tags and comments
            if '{%' in line or '{{' in line or line.strip().startswith('//'):
                continue
                
            for char_pos, char in enumerate(line):
                if char == '{':
                    brace_stack.append((line_num, char_pos, char))
                elif char == '}':
                    if brace_stack:
                        brace_stack.pop()
                    else:
                        print(f"Unmatched '}}' at line {line_num}, position {char_pos}")
                elif char == '(':
                    paren_stack.append((line_num, char_pos, char))
                elif char == ')':
                    if paren_stack:
                        paren_stack.pop()
                    else:
                        print(f"Unmatched ')' at line {line_num}, position {char_pos}")
                elif char == '[':
                    bracket_stack.append((line_num, char_pos, char))
                elif char == ']':
                    if bracket_stack:
                        bracket_stack.pop()
                    else:
                        print(f"Unmatched ']' at line {line_num}, position {char_pos}")
        
        # Report unmatched opening braces
        if brace_stack:
            print(f"Unmatched opening braces: {len(brace_stack)}")
            for line_num, char_pos, char in brace_stack[-5:]:  # Show last 5
                print(f"  Line {line_num}, position {char_pos}: '{char}'")
        
        if paren_stack:
            print(f"Unmatched opening parentheses: {len(paren_stack)}")
            for line_num, char_pos, char in paren_stack[-5:]:
                print(f"  Line {line_num}, position {char_pos}: '{char}'")
        
        if bracket_stack:
            print(f"Unmatched opening brackets: {len(bracket_stack)}")
            for line_num, char_pos, char in bracket_stack[-5:]:
                print(f"  Line {line_num}, position {char_pos}: '{char}'")

if __name__ == "__main__":
    find_missing_braces('/Users/kuwatataiga/wakakusa-shift-1/cultivation/templates/cultivation/plot_floor_plan.html')