import re

def validate_user_keywords(user_keywords):
    # Regular expression pattern for allowed characters
    pattern = r'^[\w\s.-]+$'
    
    # Check if the user_keywords match the pattern
    if re.match(pattern, user_keywords):
        return user_keywords
    else:
        # Remove any characters that are not allowed
        sanitized_keywords = re.sub(r'[^\w\s.-]', ' ', user_keywords)
        return sanitized_keywords