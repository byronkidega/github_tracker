from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from github import Github
from . import db
from .models import Repository, Commit, Contributor, Issue
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
                    existing_repo.description = repo.description
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
    token = session.get("github_token")
    if not token:
        flash("GitHub token not found. Please connect again.", "danger")
        return redirect(url_for("main.connect"))

    try:
        # Fetch the LOCAL repository from your database
        local_repo = Repository.query.filter_by(owner=owner, name=repo_name).first()
        if not local_repo:
            flash("Repository not found in local database.", "danger")
            return redirect(url_for("main.repositories"))

        github_client = Github(token)
        repo = github_client.get_repo(f"{owner}/{repo_name}")  # GitHub API repo

        # Get contributor stats ONCE (outside the loop)
        contributor_stats = repo.get_stats_contributors()

        # Process all contributors from the stats
        for data in contributor_stats:
            contributor_login = data.author.login
            total_commits = data.total
            lines_added = sum(week.a for week in data.weeks)
            lines_removed = sum(week.d for week in data.weeks)

            # Handle last_contributed date (convert from Unix timestamp)
            last_contributed = None
            if data.weeks:
                latest_week = max(data.weeks, key=lambda week: week.w)
                last_contributed = latest_week.w  # Already a datetime object!

            # Check if contributor exists
            existing_contributor = Contributor.query.filter_by(
                contributor_name=contributor_login,
                repository_id=local_repo.id  # Use LOCAL repository ID
            ).first()

            if existing_contributor:
                existing_contributor.commit_count = total_commits
                existing_contributor.lines_added = lines_added
                existing_contributor.lines_removed = lines_removed
                existing_contributor.last_contributed = last_contributed
            else:
                new_contributor = Contributor(
                    repository_id=local_repo.id,  # Use LOCAL repository ID
                    contributor_name=contributor_login,
                    commit_count=total_commits,
                    lines_added=lines_added,
                    lines_removed=lines_removed,
                    last_contributed=last_contributed
                )
                db.session.add(new_contributor)

        db.session.commit()
        flash("Contributors updated successfully!", "success")

    except Exception as e:
        flash(f"Error fetching contributors: {str(e)}", "danger")

    
    return redirect(url_for("main.contributors_page", owner=owner, repo=repo_name))



@bp.route('/contributors_page/<owner>/<repo>')
def contributors_page(owner, repo):
    """Render a page showing contributors for a specific repository"""

    # Fetch the repository based on the name and owner
    repository = Repository.query.filter_by(name=repo, owner=owner).first()

    if not repository:
        flash("Repository not found.", "danger")
        return redirect(url_for('main.repositories'))  # Redirect to repositories page

    # Use repository.id to filter contributors
    contributors = Contributor.query.filter_by(repository_id=repository.id).order_by(Contributor.commit_count.desc()).all()

    return render_template('contributors_page.html', contributors=contributors, repo=repo, owner=owner)



@bp.route("/issues/<path:repo_name>", methods=["GET"])
def issues(repo_name):
    print(f"Fetching issues for repository: {repo_name}")  # Debugging
    token = session.get("github_token")
    print(f"Token from session: {token}")  # Debugging

    if not token:
        flash("Authentication token required to fetch issues.", "warning")
        return redirect(url_for("main.connect"))

    try:
        # Connect to GitHub
        github_client = Github(token)
        repo = github_client.get_repo(repo_name)
        
        # Fetch repository record from the database
        db_repo = Repository.query.filter_by(name=repo.name, owner=repo.owner.login).first()
        if not db_repo:
            db_repo = Repository(
                owner=repo.owner.login,
                name=repo.name,
                description=repo.description or "",
                created_at=repo.created_at,
                default_branch=repo.default_branch,
                stars=repo.stargazers_count,
                forks=repo.forks_count,
                open_issues=repo.open_issues_count,
                latest_commit_date=None,
            )
            db.session.add(db_repo)
            db.session.commit()

        # Fetch issues
        issues = repo.get_issues(state="all")  # Fetch both open and closed issues
        issue_data = []
        assignees = set()  # Unique assignees
        labels = set()     # Unique labels


        for issue in issues:
            assignee = issue.assignee.login if issue.assignee else "Unassigned"
            issue_labels = [label.name for label in issue.labels]
            
            issue_data.append({
                "title": issue.title,
                "state": issue.state,  # "open" or "closed"
                "assignee": assignee,
                "labels": issue_labels,
                "milestone": issue.milestone.title if issue.milestone else "No milestone",
                "created_at": issue.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                "updated_at": issue.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
                "url": issue.html_url,
            })
            
            # Add assignee and labels to sets
            assignees.add(assignee)
            labels.update(issue_labels)
            
            # Check if the issue already exists in the database
            existing_issue = Issue.query.filter_by(issue_id=issue.id).first()
            if not existing_issue:
                # Create a new issue record
                new_issue = Issue(
                    repository_id=db_repo.id,
                    issue_id=issue.id,
                    title=issue.title,
                    state=issue.state,
                    assignee=assignee,
                    labels=",".join(issue_labels),  # Store labels as a comma-separated string
                    milestone=issue.milestone.title if issue.milestone else None,
                    created_at=issue.created_at,
                    updated_at=issue.updated_at,
                    closed_at=issue.closed_at,
                    url=issue.html_url,
                )
                db.session.add(new_issue)

            db.session.commit()

        return render_template(
            "issues.html",
            repo=repo_name,
            issues=issue_data,
            user_fullname=repo.owner.name or repo.owner.login,
            assignees=sorted(assignees),  # Pass unique assignees
            labels=sorted(labels),       # Pass unique labels
        )

    except Exception as e:
        flash(f"Error fetching issues for {repo_name}: {e}", "danger")
        return redirect(url_for("main.connect"))
    
    
@bp.route('/issues_page/<owner>/<repo>', methods=['GET', 'POST'])
def issues_page(owner, repo):
    """Render a page showing issues for a specific repository with filtering options."""
    # Fetch the repository from the database
    repository = Repository.query.filter_by(owner=owner, name=repo).first()

    if not repository:
        flash("Repository not found.", "danger")
        return redirect(url_for('main.repositories'))

    # Fetch issues associated with the repository
    issues_query = Issue.query.filter_by(repository_id=repository.id)

    # Get filter values from the form
    selected_assignee = request.form.get('assignee')
    selected_label = request.form.get('label')
    selected_status = request.form.get('status')  # Added status filter

    # Apply filters if selected
    if selected_assignee:
        issues_query = issues_query.filter(Issue.assignee == selected_assignee)
    if selected_label:
        issues_query = issues_query.filter(Issue.labels.like(f'%{selected_label}%'))
    if selected_status:
        issues_query = issues_query.filter(Issue.state == selected_status)  # Filtering by status (open/closed)

    # Get filtered and ordered issues
    issues = issues_query.order_by(Issue.created_at.desc()).all()

    # Extract unique assignees and labels for filter options
    all_issues = Issue.query.filter_by(repository_id=repository.id).all()
    assignees = sorted(set(issue.assignee for issue in all_issues if issue.assignee))
    labels = sorted(set(label.strip() for issue in all_issues for label in issue.labels.split(',') if label.strip()))

    return render_template('issues_page.html', 
                           issues=issues, 
                           repo=repo, 
                           owner=owner,
                           repository=repository,
                           assignees=assignees,
                           labels=labels,
                           selected_assignee=selected_assignee,
                           selected_label=selected_label,
                           selected_status=selected_status)  # Pass selected status to the template

