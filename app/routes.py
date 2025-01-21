from flask import Blueprint, render_template, request, flash, redirect, url_for
from github import Github
from . import db
from .models import Repository
from datetime import datetime

bp = Blueprint('main', __name__)

@bp.route("/connect", methods=["GET", "POST"])
def connect():
    if request.method == "POST":
        token = request.form.get("token")
        try:
            # Connect to GitHub
            github_client = Github(token)
            user = github_client.get_user()
            
            # Fetch repositories
            repos = user.get_repos()

            # Save repositories in the database
            for repo in repos:
                if not Repository.query.filter_by(name=repo.name).first():
                    latest_commit_date = None
                    try:
                        commits = repo.get_commits()
                        if commits.totalCount > 0:
                            latest_commit_date = commits[0].commit.author.date
                    except Exception as e:
                        print(f"Error fetching commits for {repo.name}: {e}")
                        latest_commit_date = None
                    
                    # Debugging statement
                    print(f"Repository: {repo.name}, Latest Commit Date: {latest_commit_date}")

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



@bp.route("/repositories", methods=["GET"])
def repositories():
    search = request.args.get("search", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 10  # Number of repositories per page
    
    query = Repository.query
    if search:
        query = query.filter(Repository.name.ilike(f"%{search}%"))
        
    repositories = Repository.query.paginate(page=page, per_page=per_page)
    return render_template("repositories.html", repositories=repositories)

