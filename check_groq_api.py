import subprocess, json, os

api_key = os.environ.get('GROQ_API_KEY', '')
if not api_key:
    print("GROQ_API_KEY not set")
    exit(1)

result = subprocess.run(
    ['curl', '-s', 'https://api.groq.com/openai/v1/models',
     '-H', f'Authorization: Bearer {api_key}'],
    capture_output=True, text=True, timeout=15
)

try:
    d = json.loads(result.stdout)
    models = [m['id'] for m in d.get('data', [])]
    groq_prefixed = [m for m in models if m.startswith('groq/')]
    print(f"Total Groq API models: {len(models)}")
    print(f"Groq-prefixed (groq/...): {len(groq_prefixed)}")
    print("\nFirst 15 raw model IDs from Groq API:")
    for m in models[:15]:
        print(f"  {m}")
    if groq_prefixed:
        print("\nGroq-prefixed:")
        for m in groq_prefixed[:10]:
            print(f"  {m}")
except Exception as e:
    print(f"Error: {e}")
    print("Raw output:", result.stdout[:500])