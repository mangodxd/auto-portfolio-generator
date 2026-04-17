import re
import os
import json
import time
import base64
import markdown
import requests
import argparse

from dotenv import load_dotenv
from collections import Counter
from datetime import datetime, timedelta, timezone
from jinja2 import Environment, FileSystemLoader, select_autoescape

load_dotenv()

BASE_URL = "https://api.github.com"
MAX_README_LENGTH = 300
TOP_REPO_COUNT = 6
TOP_LANGUAGES_COUNT = 5
RECENT_DAYS_THRESHOLD = 90

def fetch(url, headers, retries=3, timeout=10, ignore_status_code=None):
    if ignore_status_code is None:
        ignore_status_code = []
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)

            if response.status_code == 403 and response.headers.get('x-ratelimit-remaining') == '0':
                reset_time = int(response.headers.get('x-ratelimit-reset', time.time() + 60))
                sleep_duration = max(0, reset_time - int(time.time())) + 1
                print(f"rate limit exceeded. waiting {sleep_duration} seconds until reset for {url}...")
                time.sleep(sleep_duration)             

                # Retry this request with attempt tracking.
                # On rate limit: sleep and repeat until success or max retries.
                response = requests.get(url, headers=headers, timeout=timeout)                    
                
            if response.status_code in ignore_status_code:
                return response


            response.raise_for_status()
            return response
        
        except requests.exceptions.RequestException as e:
            print(f"attempt {attempt + 1}/{retries} failed for {url}: {e}")
            if attempt == retries - 1:
                print(f"all retries failed for {url}.")
                return None
    return None

def summary_readme(markdown_text):
    if not markdown_text:
        return None
    
    blocks = markdown_text.split('\n\n')
    summary_blocks = []
    total_len = 0
    ignore_pattern = re.compile(r'^(\s*\[?!\[[^\]]+\]\([^)]+\)\]?\s*)+$|^\s*<.+>\s*$', re.IGNORECASE)

    for block in blocks:
        stripped_block = block.strip()
        if not stripped_block or ignore_pattern.match(stripped_block):
            continue
        
        # guessing meaningful text block
        if len(stripped_block) > 50 or total_len > 0:
            summary_blocks.append(block)
            total_len += len(stripped_block)
            if total_len >= MAX_README_LENGTH:
                break
                
    return markdown.markdown('\n\n'.join(summary_blocks)) if summary_blocks else None

def extract_features(markdown_text):
    "guessing features from readme"
    if not markdown_text:
        return []
    
    lines = markdown_text.split('\n')
    in_features_section = False
    features = []
    blank_lines = 0

    for line in lines:
        if re.match(r'^#{2,4}\s+.*features.*', line, re.IGNORECASE):
            in_features_section = True
            continue
        
        if in_features_section:
            if re.match(r'^#{2,4}\s+', line):
                break  # Stop at the next heading
            
            if not line.strip():
                blank_lines += 1
                if blank_lines > 1:
                    break
            else:
                blank_lines = 0
                match = re.match(r'^\s*[\-\*]\s+(.*)', line)
                if match:
                    features.append(match.group(1).strip())
                    
    return features

def RankingRepo(repo):
    """Ranking a repository based on various metrics."""
    score = 0
    score += repo.get('stargazers_count', 0) * 10
    score += repo.get('forks_count', 0) * 15
    if repo.get('description'): score += 5
    if repo.get('topics'): score += 5
    if repo.get('homepage'): score += 20
        
    pushed_at_str = repo.get('pushed_at')
    if pushed_at_str:
        try:
            pushed_at_date = datetime.strptime(pushed_at_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - pushed_at_date < timedelta(days=RECENT_DAYS_THRESHOLD):
                score += 20
        except (ValueError, TypeError) as e:
            print(f"could not parse 'pushed_at' date: {pushed_at_str}")
            print(f"error: {e}")
    return score

# ------------- Core logic -------------
class APG: #Auto Portfolio Generator
    def __init__(self, username):
        self.username = username
        self.headers = {}
        self.user_data = None
        self.repos_data = []
        self._setup_auth()

    def _setup_auth(self):
        token = os.environ.get("GITHUB_TOKEN")
        if token and token != "your_github_token_here":
            self.headers["Authorization"] = f"token {token}"
            print("using GITHUB_TOKEN for authentication.")

    def _fetching_data(self):
        print(f"starting data fetch for user: {self.username}")
        self._fetch_user_data()
        self._fetch_repos_data()
        self._process_repos()
        self._language_stats()
        print("data fetching and processing complete.")

    def _fetch_user_data(self):
        user_url = f"{BASE_URL}/users/{self.username}"
        response = fetch(user_url, self.headers)
        if not response:
            raise Exception("failed to fetch user data. Check username and network.")
        self.user_data = response.json()

    def _fetch_repos_data(self):
        repos_url = f"{BASE_URL}/users/{self.username}/repos?per_page=100&sort=pushed"
        response = fetch(repos_url, self.headers)
        if response:
            self.repos_data = response.json()
        
        # Basic pagination handling (can be extended)
        if response and 'next' in response.links:
            next_url = response.links['next']['url']
            print(f"fetching next page of repos: {next_url}")
            next_response = fetch(next_url, self.headers)
            if next_response:
                self.repos_data.extend(next_response.json())

    def _process_repos(self):
        """Filters, enriches, and scores each repository."""
        self.user_data['total_stars'] = sum(r.get('stargazers_count', 0) for r in self.repos_data if not r.get('fork'))
        # remove forks and empty repositories
        base_filtered = [r for r in self.repos_data if not r.get('fork') and r.get('size', 0) > 0]
        
        for repo in base_filtered:
            repo['score'] = RankingRepo(repo)
            
        # keep if score >= 5 (has description, topics, stars, homepage, or recently pushed)
        filtered = [r for r in base_filtered if r['score'] >= 5]

        for repo in filtered:
            print(f"processing repository: {repo['name']}")

            # fetch repo languages data for chart
            lang_url = repo.get('languages_url')
            lang_resp = fetch(lang_url, self.headers) if lang_url else None
            repo['languages_dict'] = lang_resp.json() if lang_resp else {}
            
            # processing readme summarizing and feature extraction
            readme_url = f"{BASE_URL}/repos/{self.username}/{repo['name']}/readme"
            try:
                readme_resp = fetch(readme_url, self.headers, ignore_status_code=[404])
                
                if not readme_resp:
                    print(f"failed to fetch README for {repo['name']}")
                    repo['readme_summary'], repo['extracted_features'] = None, []
                elif readme_resp.status_code == 404:
                    print(f"repository '{repo['name']}' has no README file.")
                    repo['readme_summary'], repo['extracted_features'] = None, []
                else:
                    content = base64.b64decode(readme_resp.json()['content']).decode('utf-8')
                    repo['readme_summary'] = summary_readme(content)
                    repo['extracted_features'] = extract_features(content)
            except (KeyError, base64.binascii.Error, UnicodeDecodeError) as e:
                print(f"could not parse README for {repo['name']}: {e}")
                repo['readme_summary'], repo['extracted_features'] = None, []
        
        # Sort repos by README followed by stars, then score
        self.repos_data = sorted(
            filtered, 
            key=lambda r: (
                1 if r.get('readme_summary') else 0,
                r.get('stargazers_count', 0),
                r.get('score', 0)
            ), 
            reverse=True
        )

    def _language_stats(self):
        lang_counter = Counter()
        for repo in self.repos_data:
            for lang, size in repo.get('languages_dict', {}).items():
                lang_counter[lang] += size
        
        total_bytes = sum(lang_counter.values())
        top_languages = []
        if total_bytes > 0:
            for lang, size in lang_counter.most_common(TOP_LANGUAGES_COUNT):
                top_languages.append({
                    "language": lang,
                    "percentage": round((size / total_bytes) * 100, 1)
                })
        self.user_data['global_languages_json'] = json.dumps(top_languages)

    def render_website(self):
        if not self.user_data:
            print("no user data fetched. Cannot render.")
            return

        env = Environment(
            loader=FileSystemLoader("templates"),
            autoescape=select_autoescape(['html', 'xml'])
        )

        output_dir = os.path.join("output", self.username)
        os.makedirs(output_dir, exist_ok=True)
        
        templates_to_render = {
            "index.html": {"repos": self.repos_data[:TOP_REPO_COUNT]},
            "projects.html": {"repos": self.repos_data}
        }

        for template_name, context in templates_to_render.items():
            try:
                template = env.get_template(template_name)
                full_context = {"user": self.user_data, **context}
                output_path = os.path.join(output_dir, template_name)
                
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(template.render(full_context))
                print(f"successfully rendered {output_path}")
            except Exception as e:
                print(f"error rendering template {template_name}: {e}")

def main():
    """Main function to run the portfolio generator."""
    parser = argparse.ArgumentParser(description="Generate a GitHub Portfolio from user data.")
    parser.add_argument("--user", required=True, help="GitHub username to generate the portfolio for.")
    args = parser.parse_args()

    try:
        generator = APG(args.user)
        generator._fetching_data()
        generator.render_website()
        print(f"\nportfolio generation complete -> ./output/{args.user}/index.html")
    except Exception as e:
        print(f"a critical error occurred: {e}")
        print(f"\nfailed to generate portfolio. See logs for details.")

if __name__ == "__main__":
    main()