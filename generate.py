import requests
import argparse
import os
import base64
import markdown
import logging
import json
import re
import time
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from collections import Counter
from jinja2 import Environment, FileSystemLoader, select_autoescape

load_dotenv()

# --- Constants ---
BASE_URL = "https://api.github.com"
README_SUMMARY_LENGTH = 300
TOP_REPO_COUNT = 6
TOP_LANGUAGES_COUNT = 8
RECENT_DAYS_THRESHOLD = 90

# --- Project Type Detection ---
PROJECT_TYPE_KEYWORDS = {
    "frontend": [
        "react", "vue", "angular", "svelte", "next", "nuxt", "gatsby",
        "css", "html", "tailwind", "bootstrap", "sass", "scss", "ui",
        "landing", "website", "portfolio", "blog", "theme", "template"
    ],
    "backend": [
        "api", "server", "rest", "graphql", "microservice", "database",
        "auth", "middleware", "endpoint", "fastapi", "express", "django",
        "flask", "spring", "laravel", "rails", "nest"
    ],
    "fullstack": [
        "fullstack", "full-stack", "mern", "mean", "lamp",
        "web app", "webapp", "dashboard", "admin", "panel", "saas"
    ],
    "cli": [
        "cli", "command line", "terminal", "console", "tool",
        "utility", "automation", "script", "batch"
    ],
    "library": [
        "library", "package", "module", "sdk", "wrapper",
        "wrapper", "helper", "utils", "shared", "common"
    ],
    "mobile": [
        "mobile", "android", "ios", "react native", "flutter",
        "swift", "kotlin", "app store", "play store"
    ],
    "data": [
        "data", "machine learning", "ml", "ai", "analytics",
        "visualization", "scraping", "crawler", "etl", "pipeline",
        "neural", "model", "dataset"
    ],
    "devops": [
        "docker", "kubernetes", "ci/cd", "devops", "terraform",
        "ansible", "aws", "azure", "gcp", "deploy", "nginx"
    ]
}

# --- Tech Stack Detection ---
TECH_STACK_PATTERNS = {
    "React": ["react", "jsx", "tsx", "next.js", "nextjs"],
    "Vue": ["vue", "vuejs", "nuxt", "nuxtjs"],
    "Angular": ["angular", "ng"],
    "Svelte": ["svelte", "sveltekit"],
    "TypeScript": ["typescript", "ts"],
    "Python": ["python", "pip", "conda"],
    "Node.js": ["node", "nodejs", "express", "fastify"],
    "Go": ["golang", "go"],
    "Rust": ["rust", "cargo"],
    "Java": ["java", "spring", "maven", "gradle"],
    "C#": ["csharp", "c#", ".net", "dotnet"],
    "PHP": ["php", "laravel", "symfony", "composer"],
    "Ruby": ["ruby", "rails", "rubygems"],
    "Swift": ["swift", "ios", "xcode"],
    "Kotlin": ["kotlin", "android"],
    "Flutter": ["flutter", "dart"],
    "Docker": ["docker", "container"],
    "PostgreSQL": ["postgres", "postgresql", "psql"],
    "MongoDB": ["mongo", "mongodb", "mongoose"],
    "Redis": ["redis", "cache"],
    "Tailwind": ["tailwind", "tailwindcss"],
    "GraphQL": ["graphql", "gql"],
    "REST": ["rest", "restapi", "restful"],
}

# --- Smart Patterns ---
QUALITY_SIGNALS = {
    "has_tests": [r"test", r"spec", r"__tests__", r"jest", r"pytest", r"mocha", r"cypress"],
    "has_ci": [r"\.github/workflows", r"\.gitlab-ci", r"travis", r"circleci", r"jenkins"],
    "has_docs": [r"docs/", r"documentation", r"wiki", r"jsdoc", r"sphinx"],
    "has_changelog": [r"changelog", r"changes", r"release"],
    "has_license": [r"license"],
    "has_contributing": [r"contributing"],
    "has_docker": [r"dockerfile", r"docker-compose"],
}

# --- Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# --- Helper Functions ---

def fetch_with_retry(url, headers, retries=3, timeout=10, ignore_status=None):
    if ignore_status is None:
        ignore_status = []

    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)

            if response.status_code == 403 and response.headers.get('x-ratelimit-remaining') == '0':
                reset_time = int(response.headers.get('x-ratelimit-reset', time.time() + 60))
                sleep_duration = max(0, reset_time - int(time.time())) + 1
                logging.warning(f"Rate limit hit. Sleeping {sleep_duration}s...")
                time.sleep(sleep_duration)
                response = requests.get(url, headers=headers, timeout=timeout)

            if response.status_code in ignore_status:
                return response

            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logging.warning(f"Attempt {attempt + 1}/{retries} failed for {url}: {e}")
            if attempt == retries - 1:
                return None
    return None


def detect_project_type(repo, readme_content=""):
    """Detect project type from description, topics, languages, and README."""
    text = " ".join([
        (repo.get("description") or "").lower(),
        " ".join(repo.get("topics", [])).lower(),
        " ".join(repo.get("languages_dict", {}).keys()).lower(),
        readme_content[:2000].lower()
    ])

    scores = {}
    for ptype, keywords in PROJECT_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[ptype] = score

    if not scores:
        return "other"

    return max(scores, key=scores.get)


def detect_tech_stack(repo, readme_content=""):
    """Detect tech stack from languages, topics, and README."""
    stack = set()

    # From languages
    for lang in repo.get("languages_dict", {}).keys():
        for tech, patterns in TECH_STACK_PATTERNS.items():
            if lang.lower() in [p.lower() for p in patterns]:
                stack.add(tech)

    # From topics
    for topic in repo.get("topics", []):
        topic_lower = topic.lower()
        for tech, patterns in TECH_STACK_PATTERNS.items():
            if any(p in topic_lower for p in patterns):
                stack.add(tech)

    # From README (limited scan)
    readme_lower = readme_content[:3000].lower()
    for tech, patterns in TECH_STACK_PATTERNS.items():
        if any(p in readme_lower for p in patterns):
            stack.add(tech)

    return sorted(stack)[:6]


def extract_features_smart(readme_content):
    """Extract features using multiple strategies."""
    if not readme_content:
        return []

    features = []
    lines = readme_content.split("\n")

    # Strategy 1: Look for Features section
    in_section = False
    for line in lines:
        if re.match(r"^#{1,4}\s+.*feature", line, re.IGNORECASE):
            in_section = True
            continue
        if in_section:
            if re.match(r"^#{1,4}\s+", line):
                break
            match = re.match(r"^\s*[-*]\s+(.*)", line)
            if match and len(match.group(1).strip()) > 10:
                features.append(match.group(1).strip())

    if features:
        return features[:4]

    # Strategy 2: Look for bullet points after any section heading
    in_section = False
    for line in lines:
        if re.match(r"^#{1,4}\s+", line):
            in_section = True
            continue
        if in_section:
            match = re.match(r"^\s*[-*]\s+(.*)", line)
            if match and len(match.group(1).strip()) > 15:
                features.append(match.group(1).strip())
                if len(features) >= 3:
                    break
            if not line.strip():
                continue

    return features[:3]


def extract_readme_summary(markdown_text):
    """Extract a concise summary from README."""
    if not markdown_text:
        return None

    blocks = markdown_text.split("\n\n")
    summary_blocks = []
    total_len = 0
    ignore_pattern = re.compile(
        r"^(\s*\[?!\[[^\]]+\]\([^)]+\)\]?\s*)+$|^\s*<.+>\s*$",
        re.IGNORECASE
    )

    for block in blocks:
        stripped = block.strip()
        if not stripped or ignore_pattern.match(stripped):
            continue
        if len(stripped) > 40 or total_len > 0:
            summary_blocks.append(block)
            total_len += len(stripped)
            if total_len >= README_SUMMARY_LENGTH:
                break

    return markdown.markdown("\n\n".join(summary_blocks)) if summary_blocks else None


def check_quality_signals(readme_content):
    """Check for quality signals in the repo."""
    signals = {}
    readme_lower = readme_content.lower() if readme_content else ""
    for signal, patterns in QUALITY_SIGNALS.items():
        signals[signal] = any(re.search(p, readme_lower, re.IGNORECASE) for p in patterns)
    return signals


def calculate_repo_score(repo):
    """Smart scoring system for repositories."""
    score = 0

    # Base metrics
    score += repo.get("stargazers_count", 0) * 10
    score += repo.get("forks_count", 0) * 15

    # Description quality
    desc = repo.get("description") or ""
    if len(desc) > 50:
        score += 10
    elif len(desc) > 20:
        score += 5

    # Topics
    topics = repo.get("topics", [])
    score += min(len(topics) * 3, 15)

    # Homepage
    if repo.get("homepage"):
        score += 20

    # Recency
    pushed_at = repo.get("pushed_at")
    if pushed_at:
        try:
            pushed_date = datetime.strptime(pushed_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            days_since = (datetime.now(timezone.utc) - pushed_date).days
            if days_since < 30:
                score += 30
            elif days_since < 90:
                score += 20
            elif days_since < 180:
                score += 10
        except (ValueError, TypeError):
            pass

    # Size (not too small, not too big)
    size = repo.get("size", 0)
    if 10 < size < 50000:
        score += 10

    # Quality signals from README
    quality = repo.get("quality_signals", {})
    score += sum(5 for v in quality.values() if v)

    # Has features
    if repo.get("extracted_features"):
        score += 10

    # Has README summary
    if repo.get("readme_summary"):
        score += 5

    # Language diversity
    langs = repo.get("languages_dict", {})
    if len(langs) >= 3:
        score += 5

    return score


# --- Core Logic ---

class GitHubPortfolioGenerator:
    def __init__(self, username):
        self.username = username
        self.headers = {}
        self.user_data = None
        self.repos_data = []
        self.now = datetime.now()
        self._setup_auth()

    def _setup_auth(self):
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            self.headers["Authorization"] = f"token {token}"
            logging.info("Using GITHUB_TOKEN for authentication.")

    def fetch_all_data(self):
        logging.info(f"Starting data fetch for user: {self.username}")
        self._fetch_user_data()
        self._fetch_repos_data()
        self._process_repos()
        self._calculate_language_stats()
        self._build_skills_overview()
        self._build_project_categories()
        logging.info("Data fetching and processing complete.")

    def _fetch_user_data(self):
        response = fetch_with_retry(f"{BASE_URL}/users/{self.username}", self.headers)
        if not response:
            raise Exception("Failed to fetch user data.")
        self.user_data = response.json()

    def _fetch_repos_data(self):
        response = fetch_with_retry(
            f"{BASE_URL}/users/{self.username}/repos?per_page=100&sort=pushed",
            self.headers
        )
        if response:
            self.repos_data = response.json()
            if 'next' in response.links:
                next_response = fetch_with_retry(response.links['next']['url'], self.headers)
                if next_response:
                    self.repos_data.extend(next_response.json())

    def _process_repos(self):
        self.user_data["total_stars"] = sum(
            r.get("stargazers_count", 0) for r in self.repos_data if not r.get("fork")
        )

        base_filtered = [r for r in self.repos_data if not r.get("fork") and r.get("size", 0) > 0]

        for repo in base_filtered:
            repo["score"] = calculate_repo_score(repo)

        filtered = [r for r in base_filtered if r["score"] >= 5]

        for repo in filtered:
            logging.info(f"Processing: {repo['name']}")

            # Fetch languages
            lang_resp = fetch_with_retry(repo.get("languages_url"), self.headers) if repo.get("languages_url") else None
            repo["languages_dict"] = lang_resp.json() if lang_resp else {}

            # Fetch README
            readme_content = ""
            readme_url = f"{BASE_URL}/repos/{self.username}/{repo['name']}/readme"
            try:
                readme_resp = fetch_with_retry(readme_url, self.headers, ignore_status=[404])
                if readme_resp and readme_resp.status_code != 404:
                    readme_content = base64.b64decode(readme_resp.json()["content"]).decode("utf-8")
                    repo["readme_summary"] = extract_readme_summary(readme_content)
                else:
                    repo["readme_summary"] = None
            except (KeyError, base64.binascii.Error, UnicodeDecodeError) as e:
                logging.warning(f"Could not parse README for {repo['name']}: {e}")
                repo["readme_summary"] = None
                readme_content = ""

            # Smart extraction
            repo["extracted_features"] = extract_features_smart(readme_content)
            repo["project_type"] = detect_project_type(repo, readme_content)
            repo["tech_stack"] = detect_tech_stack(repo, readme_content)
            repo["quality_signals"] = check_quality_signals(readme_content)

            # Recalculate score with quality signals
            repo["score"] = calculate_repo_score(repo)

        # Sort: by recency first, then stars, then score
        self.repos_data = sorted(
            filtered,
            key=lambda r: (
                1 if r.get("readme_summary") or r.get("extracted_features") else 0,
                r.get("stargazers_count", 0),
                r.get("score", 0)
            ),
            reverse=True
        )

    def _calculate_language_stats(self):
        lang_counter = Counter()
        for repo in self.repos_data:
            for lang, size in repo.get("languages_dict", {}).items():
                lang_counter[lang] += size

        total_bytes = sum(lang_counter.values())
        lang_data = {}
        if total_bytes > 0:
            for lang, size in lang_counter.most_common(TOP_LANGUAGES_COUNT):
                lang_data[lang] = round((size / total_bytes) * 100, 1)
        self.user_data["lang_data_json"] = json.dumps(lang_data)

    def _build_skills_overview(self):
        """Build a skills overview from language usage."""
        lang_counter = Counter()
        for repo in self.repos_data:
            for lang, size in repo.get("languages_dict", {}).items():
                lang_counter[lang] += size

        total = sum(lang_counter.values())
        skills = []
        if total > 0:
            for lang, size in lang_counter.most_common(12):
                pct = round((size / total) * 100, 1)
                skills.append({"name": lang, "percentage": pct})

        self.user_data["skills"] = skills

        # Count project types
        type_counter = Counter(r.get("project_type", "other") for r in self.repos_data)
        self.user_data["project_type_counts"] = dict(type_counter)

    def _build_project_categories(self):
        """Group repos by project type."""
        categories = {}
        for repo in self.repos_data:
            ptype = repo.get("project_type", "other")
            if ptype not in categories:
                categories[ptype] = []
            categories[ptype].append(repo)

        # Sort categories by count
        self.user_data["categories"] = dict(
            sorted(categories.items(), key=lambda x: len(x[1]), reverse=True)
        )

    def render_website(self):
        if not self.user_data:
            logging.error("No user data. Cannot render.")
            return

        env = Environment(
            loader=FileSystemLoader("templates"),
            autoescape=select_autoescape(["html", "xml"])
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
                full_context = {
                    "user": self.user_data,
                    "now": datetime.now(),
                    **context
                }
                output_path = os.path.join(output_dir, template_name)
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(template.render(full_context))
                logging.info(f"Rendered {output_path}")
            except Exception as e:
                logging.error(f"Error rendering {template_name}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Generate a GitHub Portfolio.")
    parser.add_argument("--user", required=True, help="GitHub username.")
    args = parser.parse_args()

    try:
        generator = GitHubPortfolioGenerator(args.user)
        generator.fetch_all_data()
        generator.render_website()
        print("\nPortfolio generation complete!")
    except Exception as e:
        logging.critical(f"Critical error: {e}")
        print(f"\nFailed to generate portfolio.")


if __name__ == "__main__":
    main()
