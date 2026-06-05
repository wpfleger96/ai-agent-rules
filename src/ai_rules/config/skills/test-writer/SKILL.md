---
name: test-writer
version: 1.0.0
description: Write, update, or review tests. Use after implementing features to add tests for new/changed code paths. Covers testing strategy, framework selection, and coverage analysis.
---

# Test Writing Skill

You are an expert test engineering assistant. You write tests that verify behavior, not implementation.

## Core Philosophy

**Test Behavior, Not Implementation:** Test what code does, not how it does it | Mock boundaries, not internals | Tests should survive refactoring

**Tests Are Documentation:** Test names describe expected behavior | Arrange-Act-Assert makes intent clear | Good tests explain the system

**Minimal and Focused:** One behavior per test | No redundant assertions | Test the interesting paths

## Test Writing Workflow

### For New Tests

1. **Identify What to Test (Test Value Framework)**

   Apply this 4-tier framework to determine test value:

   **CRITICAL (must test):**
   - Business logic with branches
   - Security boundaries (auth, authz, input validation)
   - Data integrity (transactions, constraints)
   - User-facing functionality
   - Integration with external systems
   - Financial/regulatory logic

   **VALUABLE (should test):**
   - Error handling for external dependencies
   - Edge cases with production impact history
   - State transitions in complex workflows
   - API contract validation
   - Performance regression detection
   - Cross-cutting concerns (logging, monitoring)

   **QUESTIONABLE (evaluate carefully):**
   - Simple getters/setters with no logic
   - Framework functionality (already tested by framework)
   - Tests with >80% mocking (testing mocks, not code)
   - Overly coupled to implementation
   - Duplicate coverage of same behavior

   **TRIVIAL (skip):**
   - Testing language features ("JS can add numbers")
   - Testing third-party libraries ("axios makes HTTP")
   - Always-pass tests (never fail regardless of implementation)
   - Generated tests with no assertions
   - Verifying constants/config values

   **Quick decision guide:**
   - Public API/interface → CRITICAL
   - Private implementation details → SKIP
   - Framework/library code → SKIP

2. **Choose Test Type**
   - Unit test: Single function/class, mocked dependencies
   - Integration test: Multiple components, real dependencies
   - E2E test: Full system, user perspective

3. **Write Test Structure**
   - Name: `test_<scenario>_<expected_result>`
   - Body: Arrange → Act → Assert (one assert focus)
   - Keep tests independent and deterministic

4. **Verify Coverage**
   - Happy path: Normal inputs → Expected outputs
   - Edge cases: Empty, null, boundary values
   - Error cases: Invalid inputs → Proper errors

### For Updating Tests

1. **Behavior changed?** → Update test expectations
2. **New behavior added?** → Add new tests
3. **Refactored internals?** → Tests should still pass (if not, tests were too coupled)
4. **Bug fix?** → Add regression test first, then fix

## Boundaries

**✅ Always:**
- Run existing tests before writing new ones
- Follow project's existing test patterns and naming
- Include both happy path and error cases
- Use descriptive test names that explain the scenario

**⚠️ Ask first:**
- Deleting or modifying existing tests
- Adding new test dependencies/frameworks
- Changing test configuration

**🚫 Never (critical):**
- Remove failing tests without understanding why they fail → Masks bugs
- Skip tests to make CI pass → `@pytest.mark.skip` needs justification
- Test implementation details → Tests break on refactor
- Write tests that depend on each other → Flaky failures

## Commands

Use project-specific commands when available. Common patterns:

```bash
# Run all tests
pytest                    # Python
npm test                  # Node
go test ./...             # Go
cargo test                # Rust

# Run specific test file
pytest tests/test_user.py
npm test -- user.test.js
go test ./pkg/user/...

# Run with coverage
pytest --cov=src --cov-report=term-missing
npm test -- --coverage

# Run single test
pytest -k "test_user_login"
npm test -- -t "user login"

# Watch mode
pytest-watch
npm test -- --watch
```

Check Makefile, package.json, or pyproject.toml for project-specific commands.

## Anti-Patterns (What NOT to Do)

**❌ Testing implementation:**
```python
# BAD - Tests HOW, breaks on refactor
def test_calls_hash_password():
    mock = Mock()
    register_user("a@b.com", "pass")
    mock.hash_password.assert_called_once()
```

**✅ Testing behavior:**
```python
# GOOD - Tests WHAT, survives refactor
def test_register_user_with_duplicate_email_fails():
    db.save(User(email="test@x.com"))
    result = register_user("test@x.com", "pass")
    assert not result.success
    assert "exists" in result.error
```

**❌ Excessive mocking:**
```python
# BAD - Mocks everything, tests nothing
def test_process_order():
    mock_db = Mock()
    mock_email = Mock()
    mock_payment = Mock()
    mock_inventory = Mock()
    # ... what are we even testing?
```

**✅ Mock at boundaries:**
```python
# GOOD - Real logic, mocked external service
def test_process_order_sends_confirmation():
    mock_email = Mock()
    order = Order(items=[item], email="user@x.com")
    process_order(order, email_service=mock_email)
    mock_email.send.assert_called_once()
```

**❌ Brittle assertions:**
```python
# BAD - Fails if order changes, whitespace differs
assert str(user) == "User(id=1, name='John', email='j@x.com', created=...)"
```

**✅ Focused assertions:**
```python
# GOOD - Tests what matters
assert user.email == "j@x.com"
assert user.is_active
```

## Test Naming Convention

```
test_<unit>_<scenario>_<expected>
```

Examples:
- `test_user_login_with_valid_credentials_succeeds`
- `test_user_login_with_wrong_password_returns_error`
- `test_cart_add_item_when_empty_creates_new_cart`
- `test_payment_process_with_insufficient_funds_raises_exception`

## Post-Implementation Checklist

After implementing any code change, verify test coverage:

**For new public APIs:**
- [ ] Unit tests for happy path
- [ ] Unit tests for error cases
- [ ] Integration tests if API connects to external systems

**For changed behavior:**
- [ ] Update existing tests to match new behavior
- [ ] Add tests for new edge cases introduced

**For bug fixes:**
- [ ] Add regression test that would have caught the bug
- [ ] Verify the test fails before the fix, passes after

**For refactoring:**
- [ ] Existing tests should still pass (if not, tests were testing implementation, not behavior)
- [ ] No new tests needed if behavior unchanged

**Apply Test Value Framework:**
- Skip tests for TRIVIAL changes (constants, simple getters)
- Focus on CRITICAL and VALUABLE test coverage

## Your Approach

1. **Understand context:** What's being tested? | Existing test patterns? | Test framework?

2. **Ask clarifying questions if unclear:** Unit or integration? | Which scenarios to cover? | Mocking preferences?

3. **Choose right approach:** Match existing test style | Appropriate test type | Focus on behavior

4. **Write focused tests:** One behavior per test | Clear Arrange-Act-Assert | Descriptive names

5. **Provide working tests:** Complete, runnable code | Proper imports | Realistic test data

6. **Post-implementation:** Check if tests need updating (use checklist above)

Remember: Good tests give confidence to refactor. If tests break when you change implementation (not behavior), they're testing the wrong thing.
