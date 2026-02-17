# Team Collaboration Guide

## Overview

This guide explains how our team of 4 members will collaborate on the ProcureIQ hackathon project using Git and feature branches.

## Team Members & Branches

- **Akhil** → Branch: `Akhil` (Part 1: Security & Documentation)
- **Niranjan-SP** → Branch: `Niranjan-SP` (Part 2: Testing & Error Handling)
- **Visrutha** → Branch: `Visrutha` (Part 3: AI Safety & Validation)
- **Richard** → Branch: `branch-Richard` (Part 4: Deployment & DevOps)

## Workflow

### 1. Setup Your Branch

```bash
# Clone the repository (if not already done)
git clone https://github.com/ATR1285/Procure.git
cd Procure

# Fetch latest changes
git fetch origin

# Checkout your assigned branch
git checkout <your-branch-name>

# Pull latest changes
git pull origin <your-branch-name>
```

### 2. Working on Your Part

```bash
# Make sure you're on your branch
git branch

# Create/edit files as per your assigned part
# ... do your work ...

# Check what files changed
git status

# Stage specific files
git add <file1> <file2>

# Or stage all changes
git add .
```

### 3. Commit with Meaningful Messages

Use conventional commit message format:

```bash
# Format: <type>(<scope>): <description>

# Examples:
git commit -m "feat(security): Add environment variable validation on startup"
git commit -m "docs: Add problem statement and architecture diagram to README"
git commit -m "test: Add unit tests for invoice API endpoints"
git commit -m "fix(errors): Add retry logic to AI service calls"
git commit -m "feat(deploy): Add Render deployment configuration"
git commit -m "refactor(arch): Reorganize project structure"
git commit -m "chore: Update dependencies"
```

**Commit Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Adding or updating tests
- `refactor`: Code refactoring
- `chore`: Maintenance tasks
- `ci`: CI/CD changes

### 4. Push Your Changes

```bash
# Push to your branch
git push origin <your-branch-name>
```

### 5. Create Pull Request

When your part is complete:

1. Go to https://github.com/ATR1285/Procure
2. Click "Pull requests" → "New pull request"
3. Select:
   - **Base**: `main`
   - **Compare**: your branch (e.g., `Akhil`)
4. Fill in PR details:
   - **Title**: "Part 1: Security & Documentation" (use your part name)
   - **Description**: List what you completed
5. Request review from team members
6. Address review comments if any

### 6. Merge to Main

After approval:
- Merge the PR (use "Squash and merge" or "Create merge commit")
- Delete the feature branch (optional)

## Best Practices

### Commit Frequently
- Commit after completing each logical unit of work
- Don't wait until everything is done
- Small, frequent commits are better than one large commit

### Pull Before Push
```bash
# Always pull before pushing to avoid conflicts
git pull origin <your-branch-name>
git push origin <your-branch-name>
```

### Sync with Main Periodically
```bash
# Get latest changes from main
git checkout main
git pull origin main

# Merge main into your branch
git checkout <your-branch-name>
git merge main

# Resolve any conflicts, then push
git push origin <your-branch-name>
```

### Handling Merge Conflicts

If you get conflicts:

```bash
# 1. Git will mark conflicted files
git status

# 2. Open conflicted files and look for:
<<<<<<< HEAD
Your changes
=======
Their changes
>>>>>>> main

# 3. Edit the file to resolve conflicts
# 4. Remove conflict markers
# 5. Stage resolved files
git add <resolved-file>

# 6. Complete the merge
git commit

# 7. Push
git push origin <your-branch-name>
```

## Communication

### Code Review
- Review each other's PRs
- Leave constructive comments
- Use GitHub PR review features

### Questions & Discussions
- Use PR comments for code-specific questions
- Use GitHub Issues for bugs/features
- Tag team members with @username

### Daily Standup (Optional)
- What did you complete yesterday?
- What are you working on today?
- Any blockers?

## Part Assignment Summary

### Part 1 - Akhil (Branch: `Akhil`)
**Focus**: Security & Documentation  
**Deliverables**:
- Security audit and hardening
- Enhanced README with architecture diagram
- Security documentation
- API documentation

**Commit Prefix**: `feat(security):`, `docs:`, `refactor(arch):`

### Part 2 - Niranjan-SP (Branch: `Niranjan-SP`)
**Focus**: Testing & Error Handling  
**Deliverables**:
- Comprehensive test suite (pytest)
- Enhanced error handling
- CI/CD test integration
- Test coverage reporting

**Commit Prefix**: `test:`, `fix(errors):`, `feat(validation):`

### Part 3 - Visrutha (Branch: `Visrutha`)
**Focus**: AI Safety & Validation  
**Deliverables**:
- AI output validation & guardrails
- Prompt injection detection
- AI safety documentation
- Open-source LLM enhancement

**Commit Prefix**: `feat(ai):`, `feat(safety):`, `refactor(llm):`

### Part 4 - Richard (Branch: `branch-Richard`)
**Focus**: Deployment & DevOps  
**Deliverables**:
- Production deployment (Render/Railway)
- Enhanced CI/CD pipeline
- Production readiness
- Health checks & monitoring

**Commit Prefix**: `feat(deploy):`, `ci:`, `chore:`

## Timeline

### Phase 1 (Days 1-2): Individual Work
- Each team member works on their assigned branch
- Commit incrementally
- Push updates regularly

### Phase 2 (Days 2-3): Integration
- Create Pull Requests
- Code review
- Address feedback

### Phase 3 (Days 3-4): Merge & Test
- Merge PRs to main
- Test integrated system
- Fix integration issues

### Phase 4 (Days 4-5): Deployment & Polish
- Complete deployment (Part 4)
- Final testing on live URL
- Documentation updates
- Final submission

## Helpful Git Commands

```bash
# See commit history
git log --oneline -20

# See your changes
git diff

# Undo unstaged changes to a file
git checkout -- <file>

# Undo last commit (keep changes)
git reset --soft HEAD~1

# See remote branches
git branch -r

# See all branches
git branch -a

# Delete local branch (after merging)
git branch -d <branch-name>

# Force pull (careful!)
git fetch origin
git reset --hard origin/<your-branch>
```

## Support

If you need help:
- Ask in team chat
- Tag @ATR1285 in GitHub
- Check Git documentation: https://git-scm.com/doc

Happy coding! 🚀
