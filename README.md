# GitHub Portfolio Auto-Generator (APG)

A powerful, automated tool that generates a stunning, modern portfolio website directly from your GitHub profile. Showcase your projects, contributions, and coding skills with minimal effort.

## Features

- **Automatic Portfolio Generation**: Convert your GitHub profile into a beautiful, fully-functional portfolio website in seconds
- **Smart Repository Ranking**: Intelligently sorts repositories by README quality, stars, and activity metrics
- **Language Analytics**: Visual breakdown of your top programming languages with an interactive doughnut chart
- **GitHub Profile Integration**: Automatically fetches and displays your GitHub stats, bio, location, and social links
- **Responsive Design**: Mobile-first, fully responsive layout that works perfectly on all devices
- **Modern UI**: Built with Bootstrap 5 and custom CSS featuring glassmorphism effects and smooth animations
- **README Processing**: Automatically extracts and displays README summaries and key features from your best projects
- **Smooth Animations**: AOS (Animate On Scroll) integration for elegant scroll-triggered animations
- **Social Links**: Automatically adds GitHub, website, and Twitter links to your portfolio footer
- **Dark Mode**: Modern dark theme that's easy on the eyes and professional-looking

## Quick Start

### Prerequisites

- Python 3.8+
- GitHub account
- GitHub Personal Access Token (optional but recommended for higher API rate limits)

### Installation

1. **Clone or download** this project:
```bash
git clone https://github.com/yourusername/apg.git
cd apg
```

2. **Install dependencies**:
```bash
pip install requests jinja2 python-dotenv markdown
```

3. **Set up authentication** (optional but recommended):
   - Create a `.env` file in the project root
   - Add your GitHub token:
   ```
   GITHUB_TOKEN=your_github_personal_access_token
   ```
   - Get a token: https://github.com/settings/tokens (needs `public_repo` scope)

### Usage

Generate your portfolio:
```bash
python generate.py --user YOUR_GITHUB_USERNAME
```

Your portfolio will be generated in `./output/YOUR_USERNAME/` directory.

**Example**:
```bash
python generate.py --user octocat
```

This creates:
- `output/octocat/index.html` - Homepage with stats and featured projects
- `output/octocat/projects.html` - Complete project listing

Open `output/YOUR_USERNAME/index.html` in your browser to view your portfolio!

## How It Works

### Data Collection
1. Fetches your GitHub user profile data (name, bio, location, company, followers, etc.)
2. Retrieves all your public repositories
3. For each repository, fetches:
   - Language statistics
   - README file content
   - Stars and fork counts
   - License information

### Repository Processing
The tool intelligently filters and ranks your repositories:
- **Filters out**: Forks and empty repositories
- **Scores** repositories based on:
  - Stars count (weighted × 10)
  - Fork count (weighted × 15)
  - Description presence (+5 points)
  - Topics (+5 points)
  - Homepage/demo link (+20 points)
  - Recent activity within 90 days (+20 points)
- **Only includes** repositories with a score ≥ 5

### Ranking Logic
Repositories are sorted by:
1. **README Quality**: Projects with comprehensive READMEs appear first
2. **Stars**: More popular projects rank higher
3. **Activity Score**: Recently updated or feature-rich projects get priority

### Language Analytics
- Calculates total bytes written in each language
- Displays top 5 languages as a percentage
- Visualized with an interactive Chart.js doughnut chart

## Portfolio Contents

### Homepage (`index.html`)
- Personal introduction with typing effect
- GitHub overview statistics (repos, followers, stars, hireable status)
- Interactive language distribution chart
- Top 6 featured projects with full details
- Responsive navigation and footer with social links

### Projects Page (`projects.html`)
- Complete listing of all ranked repositories
- Detailed cards for each project including:
  - Description
  - Stars and forks count
  - Programming languages used
  - Project topics/tags
  - README summaries or key features
  - License information
  - Last updated date
  - Links to repository and live demo

## Configuration

Customize the behavior by editing constants in `generate.py`:

```python
MAX_README_LENGTH = 300          # Characters to include in README summary
TOP_REPO_COUNT = 6               # Featured projects to display on homepage
TOP_LANGUAGES_COUNT = 5          # Top languages to show in chart
RECENT_DAYS_THRESHOLD = 90       # Days to consider a repo as "recently active"
```

## Browser Support

- Chrome/Chromium (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)
- Mobile browsers (iOS Safari, Chrome Android)

## What Gets Displayed

### Automatically Fetched from GitHub
- Profile name, bio, location, company
- Avatar/profile picture
- Public repositories count
- Followers count
- Total stars across projects
- Hireable status
- Social media links (Twitter, website/blog)

### Automatically Extracted from Repositories
- Repository name and description
- Stars and fork counts
- Programming languages
- Topics/tags
- License information
- Last updated date
- README content (first 300 characters)
- Key features (extracted from "Features" section in README)
- Live demo link (from homepage field)

## Troubleshooting

### "Rate limit exceeded"
The tool handles this automatically by waiting and retrying. To increase limits:
- Add a GitHub Personal Access Token in `.env`
- Without token: 60 requests/hour
- With token: 5,000 requests/hour

### "Failed to fetch user data"
- Verify the GitHub username is correct
- Check your internet connection
- Ensure the user profile is public

### "No repositories appear"
- Make sure you have public repositories
- Repositories must have size > 0 and not be forks
- Repositories must have a score ≥ 5 to be included

## Project Structure

```
apg/
├── generate.py              # Main generation script
├── templates/
│   ├── base.html           # Base template with navbar and footer
│   ├── index.html          # Homepage template
│   ├── projects.html       # Projects listing template
│   └── components/
│       └── repo_card.html  # Reusable repository card component
├── output/                 # Generated portfolios (created on run)
│   └── [username]/
│       ├── index.html
│       └── projects.html
└── .env                    # Environment variables (GitHub token)
```

## Technologies Used

- **Backend**: Python 3, Jinja2 templating
- **Frontend**: HTML5, CSS3, Bootstrap 5
- **APIs**: GitHub REST API
- **Libraries**:
  - `requests` - HTTP requests to GitHub API
  - `jinja2` - Template rendering
  - `markdown` - README HTML conversion
  - `chart.js` - Language statistics visualization
  - `aos` - Scroll animations
  - `typed.js` - Typing effect for name

## Example Output

The generated portfolio includes:
- Modern, responsive dark-themed design
- Animated elements for better UX
- Interactive charts and statistics
- Project cards with rich information
- Direct links to GitHub and live demos
- Social media integration
- Clean, professional presentation

## Contributing

Feel free to fork, modify, and improve this project! Some ideas:
- Add more customization options
- Support for additional social platforms
- Theme customization
- Export to different formats
- GitHub Actions integration

## License

This project is provided as-is for personal use. Feel free to modify and customize it for your needs.

## Credits

Built with love using:
- GitHub API
- Bootstrap 5
- Chart.js
- AOS (Animate On Scroll)
- Typed.js

---

**Ready to showcase your work?** Run `python generate.py --user YOUR_USERNAME` and share your portfolio!
