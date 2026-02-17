# Commit Message Conventions

## Format

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

## Type
Must be one of the following:

- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation only changes
- **style**: Changes that do not affect the meaning of the code (white-space, formatting, etc)
- **refactor**: A code change that neither fixes a bug nor adds a feature
- **test**: Adding missing tests or correcting existing tests
- **chore**: Changes to the build process or auxiliary tools
- **ci**: Changes to CI/CD configuration files and scripts
- **perf**: A code change that improves performance

## Scope (Optional)
The scope could be anything specifying the place of the commit change:

- `security`: Security-related changes
- `auth`: Authentication logic
- `api`: API endpoints
- `agent`: Autonomous agent
- `db`: Database changes
- `ai`: AI/LLM integration
- `errors`: Error handling
- `deploy`: Deployment configuration
- `docs`: Documentation

## Subject
- Use imperative, present tense: "change" not "changed" nor "changes"
- Don't capitalize first letter
- No period (.) at the end
- Limit to 50 characters

## Examples

### Good Commits ✅
```bash
feat(security): add environment variable validation on startup
fix(errors): handle network timeout in email service
docs: update README with architecture diagram
test: add unit tests for invoice matching logic
refactor(ai): extract prompt templates to separate file
ci: configure automated deployment to Render
feat(api): add health check endpoint with metrics
fix(db): prevent race condition in event queue
```

### Bad Commits ❌
```bash
Fixed stuff  # Too vague
Updated files  # Not descriptive
changes  # Not meaningful
WIP  # Work in progress - commit when done
asdf  # Random text
```

## Multi-line Commits

For more complex changes:

```bash
git commit

# Opens editor, write:
feat(ai): add prompt injection detection

- Implement input sanitization for user text
- Add regex patterns for common injection attempts  
- Log detected injection attempts for monitoring
- Add unit tests for detection logic

Closes #42
```

## Team Member Conventions

### Akhil (Part 1: Security & Docs)
```bash
feat(security): add API key rotation mechanism
docs: create architecture documentation
refactor(arch): reorganize middleware structure
```

### Niranjan-SP (Part 2: Testing & Errors)
```bash
test: add integration tests for agent workflow
fix(errors): add retry logic to database operations
feat(validation): create custom exception classes
```

### Visrutha (Part 3: AI Safety)
```bash
feat(ai): implement hallucination detection
feat(safety): add confidence scoring validation
refactor(llm): add Ollama provider selection
```

### Richard (Part 4: Deployment)
```bash
feat(deploy): add Render deployment configuration
ci: configure GitHub Actions for auto-deployment
chore: update production environment variables
```

## Verification

Before committing, verify:
- ✅ Message follows the format
- ✅ Type is correct
- ✅ Subject is clear and concise
- ✅ No typos or grammar errors

## Tools

You can use this Git hook to validate commit messages:

```bash
# .git/hooks/commit-msg
#!/bin/sh
commit_msg=$(cat "$1")
pattern="^(feat|fix|docs|style|refactor|test|chore|ci|perf)(\(.+\))?: .{1,50}$"

if ! echo "$commit_msg" | grep -qE "$pattern"; then
    echo "❌ Invalid commit message format!"
    echo "Expected: <type>(<scope>): <subject>"
    echo ""
    echo "Example: feat(api): add new endpoint for analytics"
    exit 1
fi
```

Make it executable:
```bash
chmod +x .git/hooks/commit-msg
```
