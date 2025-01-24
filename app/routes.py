from flask import Blueprint, render_template, request, flash, redirect, url_for
from github import Github
from . import db
from .models import Repository
from datetime import datetime
from flask import jsonify


bp = Blueprint('main', __name__)

@bp.route("/connect", methods=["GET", "POST"])
def connect():
    if request.method == "POST":
        print("POST request received")
        token = request.form.get("token")
        print(f"Token: {token}")
        try:
            # Connect to GitHub
            github_client = Github(token)
            user = github_client.get_user()
            print(f"Authenticated as {user.login}")

            # Test with a known repository
            test_repo_name = "byronkidega/github_tracker"  # Replace with a known repository name
            try:
                print(f"Testing with repository: {test_repo_name}")
                repo = github_client.get_repo(test_repo_name)
                commits = list(repo.get_commits())
                for commit in commits[:5]:  # Fetch and print the first 5 commits
                    print(f"Commit: {commit.commit.message}, Date: {commit.commit.author.date}")
            except Exception as e:
                print(f"Error while testing repository {test_repo_name}: {e}")

            # Fetch all repositories for further processing
            repos = list(user.get_repos())
            print(f"Fetched {len(repos)} repositories")

            # Save repositories in the database
            for repo in repos:
                print(f"Processing repository: {repo.name}")
                if not Repository.query.filter_by(name=repo.name).first():
                    latest_commit_date = None
                try:
                    commits = list(repo.get_commits())
                    if commits:
                        latest_commit_date = commits[0].commit.author.date
                        print(f"Latest commit date: {latest_commit_date}")
                    else:
                        print(f"No commits found for {repo.name}")
                except Exception as e:
                    print(f"Error fetching commits for {repo.name}: {e}")
                
                new_repo = Repository(
                    name=repo.name,
                    description=repo.description,
                    created_at=repo.created_at,
                    default_branch=repo.default_branch,
                    stars=repo.stargazers_count,
                    forks=repo.forks_count,
                    open_issues=repo.open_issues_count,
                    latest_commit_date=latest_commit_date,
                )
                db.session.add(new_repo)
            db.session.commit()

            # Fetch repositories from the database and display
            repositories = Repository.query.all()
            return render_template("repositories.html", repositories=repositories)

        except Exception as e:
            error_message = str(e)
            if "401" in error_message:
                flash("Invalid GitHub token. Please try again.", "danger")
            elif "rate limit" in error_message.lower():
                flash("GitHub API rate limit reached. Try again later.", "warning")
            else:
                flash("An unexpected error occurred: " + error_message, "danger")
            return redirect(url_for("main.connect"))

    return render_template("connect.html")


@bp.route('/repositories', methods=['GET'])
def repositories():
    # Check if the request is for JSON data
    if request.headers.get('Accept') == 'application/json':
        search_query = request.args.get('search', '')
        if search_query:
            repositories = Repository.query.filter(Repository.name.ilike(f"%{search_query}%")).all()
        else:
            repositories = Repository.query.all()
        
        # Convert repository data to JSON-serializable format
        repositories_data = [
            {
                "name": repo.name,
                "description": repo.description or "No description",
                "default_branch": repo.default_branch,
                "created_at": repo.created_at.strftime('%Y-%m-%d'),
                "stars": repo.stars,
                "forks": repo.forks,
                "open_issues": repo.open_issues,
                "latest_commit_date": repo.latest_commit_date.strftime('%Y-%m-%d') if repo.latest_commit_date else "N/A",
            }
            for repo in repositories
        ]
        return jsonify(repositories_data)
    
    # Render HTML if not requesting JSON
    return render_template('repositories.html')

