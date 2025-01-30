from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from github import Github
from . import db
from .models import Repository, Commit
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
            
            # Save token in session
            session["github_token"] = token

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

            # Save repositories and their commits in the database
            for repo in repos:
                print(f"Processing repository: {repo.name}")
                existing_repo = Repository.query.filter_by(name=repo.name).first()
                commits = list(repo.get_commits())
                if commits:
                    latest_commit_date = commits[0].commit.author.date
                else:
                    print(f"No commits found for {repo.name}")
                    
                if existing_repo:
                    print(f"Repository {repo.name} already exists in the database. Updating with newly fetched information...")
                    existing_repo.stars = repo.stargazers_count
                    existing_repo.forks = repo.forks_count
                    existing_repo.open_issues = repo.open_issues_count
                    existing_repo.latest_commit_date = latest_commit_date
                    continue
                
                # Fetch repository details
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

                # Save the repository
                new_repo = Repository(
                    owner=repo.owner.login,
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
                db.session.flush()  # Get the new repository's ID before committing

                # Save commits
                try:
                    for branch in repo.get_branches():
                        branch_name = branch.name
                        print(f"Fetching commits for branch: {branch_name}")
                        branch_commits = list(repo.get_commits(sha=branch_name))
                        for commit in branch_commits:
                            # Avoid duplicate commit entries
                            if not Commit.query.filter_by(hash=commit.sha).first():
                                new_commit = Commit(
                                    hash=commit.sha,
                                    author=commit.commit.author.name,
                                    message=commit.commit.message,
                                    date=commit.commit.author.date,
                                    branch=branch_name,
                                    repository_id=new_repo.id,
                                )
                                db.session.add(new_commit)
                except Exception as e:
                    print(f"Error fetching commits for repository {repo.name}: {e}")

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
                "owner": repo.owner,
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


@bp.route("/repository/<int:repo_id>/commits")
def view_commits(repo_id):
    repository = Repository.query.get_or_404(repo_id)
    commits = Commit.query.filter_by(repository_id=repo_id).order_by(Commit.date.desc()).all()
    return render_template("commits.html", repository=repository, commits=commits)


@bp.route("/repository/<int:repo_id>/analytics")
def commit_analytics(repo_id):
    repository = Repository.query.get_or_404(repo_id)
    commits_by_user = db.session.query(
        Commit.author, db.func.count(Commit.id)
    ).filter_by(repository_id=repo_id).group_by(Commit.author).all()

    commits_by_branch = db.session.query(
        Commit.branch, db.func.count(Commit.id)
    ).filter_by(repository_id=repo_id).group_by(Commit.branch).all()

    return render_template(
        "analytics.html",
        repository=repository,
        commits_by_user=commits_by_user,
        commits_by_branch=commits_by_branch,
    )


@bp.route("/branches/<path:repo_name>", methods=["GET"])
def branches(repo_name):
    print(f"Fetching branches for repository: {repo_name}")  # Debugging
    token = session.get("github_token")
    print(f"Token from session: {token}")  # Debugging
    if not token:
        flash("Authentication token required to fetch branches.", "warning")
        return redirect(url_for("main.connect"))

    try:
        # Connect to GitHub
        github_client = Github(token)
        repo = github_client.get_repo(repo_name)
        
        
        # Fetch the repository owner's full name
        owner = repo.owner
        repository = repo
        user_fullname = owner.name  # This fetches the user's full name
        if not user_fullname:
            user_fullname = owner.login  # Fallback to GitHub username if full name is not set
        
        
        # Fetch branch information
        branches = repo.get_branches()
        branch_data = []
        recently_merged = []
        default_branch_commits = list(repo.get_commits(repo.default_branch))

        for branch in branches:
            # Check if branch has been recently merged
            if branch.name != repo.default_branch:
                branch_commits = list(repo.get_commits(branch.name))
                if any(commit.sha in [c.sha for c in default_branch_commits] for commit in branch_commits):
                    recently_merged.append(branch.name)

            branch_data.append({
                "name": branch.name,
                "protected": branch.protected,
                "active": branch.name == repo.default_branch,
                "recently_merged": branch.name in recently_merged,
            })

        return render_template("branches.html", repo=repo_name, branches=branch_data, user_fullname=user_fullname, repository=repository)

    except Exception as e:
        flash(f"Error fetching branches for {repo_name}: {e}", "danger")
        return redirect(url_for("main.connect"))


