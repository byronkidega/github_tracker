from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from github import Github
from . import db
from .models import Repository, Commit, Contributor
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




@bp.route("/commits/<path:repo_name>", methods=["GET"])
def commits(repo_name):
    print(f"Fetching commits for repository: {repo_name}")  # Debugging
    token = session.get("github_token")
    print(f"Token from session: {token}")  # Debugging
    if not token:
        flash("Authentication token required to fetch commits.", "warning")
        return redirect(url_for("main.connect"))

    try:
        # Connect to GitHub
        github_client = Github(token)
        repo = github_client.get_repo(repo_name)

        # Fetch the repository owner's full name
        owner = repo.owner
        repository = repo
        user_fullname = owner.name if owner.name else owner.login  # Fallback to GitHub username if full name is not set

        # Get repository record from DB or create if not exists
        db_repo = Repository.query.filter_by(name=repo.name, owner=owner.login).first()
        if not db_repo:
            db_repo = Repository(
                owner=owner.login,
                name=repo.name,
                description=repo.description or "",
                created_at=repo.created_at,
                default_branch=repo.default_branch,
                stars=repo.stargazers_count,
                forks=repo.forks_count,
                open_issues=repo.open_issues_count,
                latest_commit_date=None
            )
            db.session.add(db_repo)
            db.session.commit()

        # Fetch all branches to map commits
        branches = {branch.name: branch for branch in repo.get_branches()}

        # Fetch commit information
        commits = repo.get_commits()
        commit_data = []

        for commit in commits:
            branch_name = None
            for branch in branches:
                if commit.sha in [c.sha for c in repo.get_commits(branch)]:
                    branch_name = branch
                    break  # Stop once we find the first matching branch

            commit_record = Commit.query.filter_by(hash=commit.sha).first()
            if not commit_record:
                commit_record = Commit(
                    hash=commit.sha,
                    author=commit.commit.author.name if commit.commit.author else "Unknown",
                    message=commit.commit.message,
                    date=commit.commit.author.date if commit.commit.author else None,
                    branch=branch_name or repo.default_branch,
                    repository=db_repo
                )
                db.session.add(commit_record)

            commit_data.append({
                "sha": commit.sha,
                "author": commit.commit.author.name if commit.commit.author else "Unknown",
                "message": commit.commit.message,
                "date": commit.commit.author.date.strftime('%Y-%m-%d %H:%M:%S') if commit.commit.author else "Unknown",
                "url": commit.html_url,
                "branch": branch_name or repo.default_branch
            })

        # Update latest commit date for the repository
        if commit_data:
            latest_commit_date = max(commit.date for commit in Commit.query.filter_by(repository=db_repo))
            db_repo.latest_commit_date = latest_commit_date
            db.session.commit()

        return render_template("commits.html", repo=repo_name, commits=commit_data, user_fullname=user_fullname, repository=repository)

    except Exception as e:
        db.session.rollback()
        flash(f"Error fetching commits for {repo_name}: {e}", "danger")
        return redirect(url_for("main.connect"))



@bp.route('/commits_page/<owner>/<repo>')
def commits_page(owner, repo):
    """Render a page showing commits for a specific repository"""

    # Fetch the repository based on the name and owner
    repository = Repository.query.filter_by(name=repo).first()

    if not repository:
        flash("Repository not found.", "danger")
        return redirect(url_for('repositories.html'))  # Redirect to a valid page

    # Use repository.id to filter commits
    commits = Commit.query.filter_by(repository_id=repository.id).order_by(Commit.date.desc()).all()

    return render_template('commits_page.html', commits=commits, repo=repo, owner=owner)




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


@bp.route("/contributors/<owner>/<repo_name>")
def contributors(owner, repo_name):
    token = session.get("github_token")  # Retrieve token from session
    if not token:
        flash("GitHub token not found. Please connect again.", "danger")
        return redirect(url_for("main.connect"))

    try:
        github_client = Github(token)
        repo = github_client.get_repo(f"{owner}/{repo_name}")
        contributors = repo.get_contributors()

        contributor_data_list = []  # List to hold contributor data

        for contributor in contributors:
            print(f"Contributor: {contributor.login}")
            # Get the contributor's stats
            contributor_data = repo.get_stats_contributors()

            # Initialize variables to track the contributor's stats
            total_commits = 0
            lines_added = 0
            lines_removed = 0
            last_contributed = None

            # Find the contributor's stats
            for data in contributor_data:
                if data.author.login == contributor.login:
                    total_commits = data.total
                    lines_added = sum(week.a for week in data.weeks)
                    lines_removed = sum(week.d for week in data.weeks)
                    # Get the most recent commit date
                    if data.weeks:
                        last_contributed = max(week.w for week in data.weeks)

            # Prepare contributor info for display
            contributor_info = {
                "login": contributor.login,
                "total_commits": total_commits,
                "lines_added": lines_added,
                "lines_removed": lines_removed,
                "last_contributed": last_contributed
            }

            contributor_data_list.append(contributor_info)

            # Check if the contributor already exists in the database
            existing_contributor = Contributor.query.filter_by(
                contributor_name=contributor.login, repository_id=repo.id
            ).first()
            
            if existing_contributor:
                existing_contributor.commit_count = total_commits
                existing_contributor.lines_added = lines_added
                existing_contributor.lines_removed = lines_removed
                existing_contributor.last_contributed = last_contributed
            else:
                # Create a new contributor record
                new_contributor = Contributor(
                    repository_id=repo.id,
                    contributor_name=contributor.login,
                    commit_count=total_commits,
                    lines_added=lines_added,
                    lines_removed=lines_removed,
                    last_contributed=last_contributed
                )
                db.session.add(new_contributor)
        
        db.session.commit()
        flash(f"Contributors for {repo_name} updated successfully!", category="success")

    except Exception as e:
        flash(f"Error fetching contributors: {str(e)}", "danger")

    # Render the contributors template and pass the contributor data
    return render_template("contributors.html", owner=owner, repo_name=repo_name, contributors=contributor_data_list)
