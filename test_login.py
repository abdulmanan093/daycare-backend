import os
from supabase import create_client

url = 'https://rzzozbucvjjxscjvocjn.supabase.co'
key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJ6em96YnVjdmpqeHNjanZvY2puIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk3MDQyODIsImV4cCI6MjA4NTI4MDI4Mn0.sdqthAgfV9X9YZIxv4VZuCBuxkX10UT-IBke2sKpefA'

print('Creating client...')
supabase = create_client(url, key)
print('Client created. Attempting invalid login...')
try:
    res = supabase.auth.sign_in_with_password({'email': 'test@example.com', 'password': 'wrongpassword123'})
    print(res)
except Exception as e:
    print('Exception:', str(e))
