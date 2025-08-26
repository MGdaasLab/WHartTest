# Contributing to WHartTest Vue

Thank you for your interest in contributing to WHartTest Vue! This document provides guidelines and information about our development workflow.

## Branch Strategy

We use a three-branch workflow to ensure code quality and stable releases:

### Branch Descriptions

- **`master`** 🚀
  - Production-ready code only
  - Protected branch with strict rules
  - Only accepts merges from `release` branch
  - Automatically tagged for releases

- **`release`** 🧪
  - Release candidate branch
  - Used for final testing and bug fixes
  - Merges from `dev` branch
  - After testing, merges to `master`

- **`dev`** 🔧
  - Main development branch
  - All feature branches merge here
  - Integration testing happens here
  - Should always be in a working state

### Workflow Process

```
1. Create feature branch from dev
   git checkout dev
   git pull origin dev
   git checkout -b feature/your-feature-name

2. Develop your feature
   - Write code
   - Add tests if applicable
   - Update documentation

3. Submit Pull Request to dev
   - Ensure CI passes
   - Request code review
   - Address feedback

4. Release Process (Maintainers only)
   dev → release → master
```

## Development Guidelines

### Code Style

- Follow TypeScript best practices
- Use ESLint and Prettier configurations
- Write meaningful commit messages
- Add JSDoc comments for complex functions

### Commit Message Format

```
type(scope): description

Examples:
feat(auth): add user login functionality
fix(ui): resolve button alignment issue
docs(readme): update installation instructions
```

### Pull Request Guidelines

1. **Title**: Clear and descriptive
2. **Description**: Explain what and why
3. **Testing**: Describe how you tested
4. **Screenshots**: For UI changes
5. **Breaking Changes**: Clearly marked

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring
- `test/description` - Adding tests

## Setting Up Development Environment

1. **Clone the repository**
   ```bash
   git clone http://code.mgdaas-int.com/MGdaas-Lab/wheatsmarttest-vue.git
   cd wheatsmarttest-vue
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Start development server**
   ```bash
   npm run dev
   ```

4. **Run tests**
   ```bash
   npm test
   ```

## Branch Protection Rules (for maintainers)

### Master Branch
- Require pull request reviews
- Require status checks to pass
- Require branches to be up to date
- Restrict pushes to admins only

### Release Branch
- Require pull request reviews
- Require status checks to pass
- Allow merge commits

### Dev Branch
- Require status checks to pass
- Allow squash merging

## Release Process

1. **Prepare Release**
   ```bash
   git checkout release
   git merge dev
   git push origin release
   ```

2. **Test Release Candidate**
   - Deploy to staging environment
   - Run integration tests
   - Perform manual testing

3. **Deploy to Production**
   ```bash
   git checkout master
   git merge release
   git tag v1.x.x
   git push origin master --tags
   ```

4. **Sync Dev Branch**
   ```bash
   git checkout dev
   git merge master
   git push origin dev
   ```

## Getting Help

- 📖 Check existing documentation
- 🐛 Search existing issues
- 💬 Join our discussions
- 📧 Contact maintainers

## Code of Conduct

Please be respectful and professional in all interactions. We're here to build something great together!

---

Thank you for contributing to WHartTest Vue! 🎉
