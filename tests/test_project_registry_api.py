"""
API Tests for Project Registry and Claude Settings CRUD
Task: task-project-registry
"""
import sys
import json
import requests

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = None
TEST_IDS = {"project": [], "settings": []}


def login():
    global TOKEN
    r = requests.post(f"{BASE_URL}/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    data = r.json()
    assert data["code"] == 0
    TOKEN = data["data"]["access_token"]
    print(f"[LOGIN] Token obtained")
    return TOKEN


def headers():
    return {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


# ========== PROJECT TESTS ==========

def test_create_project():
    print("\n=== TEST: Create Project ===")
    payload = {
        "name": "test-project-api",
        "display_name": "Test Project",
        "description": "A test project for API testing",
        "git_repo_url": "https://github.com/test/test-repo.git",
        "git_branch": "main",
        "git_auth_username": "testuser",
        "git_auth_token": "test-token-123",
        "clone_path": "/tmp/test-clone",
        "system_prompt": "You are a test assistant",
        "fix_timeout_minutes": 60
    }
    r = requests.post(f"{BASE_URL}/projects/", json=payload, headers=headers())
    assert r.status_code == 200, f"Status: {r.status_code}, body: {r.text}"
    data = r.json()
    assert data["code"] == 0, f"Response: {data}"
    assert "id" in data["data"], f"No id in response: {data}"
    assert data["data"]["name"] == "test-project-api"
    pid = data["data"]["id"]
    TEST_IDS["project"].append(pid)
    print(f"[PASS] Created project id={pid}")

    # Duplicate name should fail
    r2 = requests.post(f"{BASE_URL}/projects/", json=payload, headers=headers())
    data2 = r2.json()
    assert data2["code"] != 0
    print(f"[PASS] Duplicate name rejected: {data2['message']}")

    # Empty git URL should fail
    r3 = requests.post(f"{BASE_URL}/projects/", json={"name": "test-empty-url", "git_repo_url": "   "}, headers=headers())
    data3 = r3.json()
    assert data3["code"] != 0
    print(f"[PASS] Empty git URL rejected: {data3['message']}")


def test_list_projects():
    print("\n=== TEST: List Projects ===")
    r = requests.get(f"{BASE_URL}/projects/", headers=headers())
    assert r.status_code == 200
    data = r.json()
    assert data["code"] == 0
    projects = data["data"]
    assert isinstance(projects, list)
    print(f"[PASS] List returned {len(projects)} projects")

    # Check sensitive fields not in list
    for p in projects:
        assert "git_auth_token" not in p, f"git_auth_token exposed!"
        assert "git_auth_username" not in p, f"git_auth_username exposed!"
    print(f"[PASS] No sensitive fields in list response")

    # Search
    r3 = requests.get(f"{BASE_URL}/projects/?search=test-project-api", headers=headers())
    data3 = r3.json()
    found = any("test-project-api" in p.get("name", "") for p in data3["data"])
    assert found
    print(f"[PASS] Search by name works")


def test_get_project():
    print("\n=== TEST: Get Project Detail ===")
    if not TEST_IDS["project"]:
        print("[SKIP] No project to retrieve")
        return
    pid = TEST_IDS["project"][0]
    r = requests.get(f"{BASE_URL}/projects/{pid}", headers=headers())
    assert r.status_code == 200
    data = r.json()
    assert data["code"] == 0
    p = data["data"]
    assert p["name"] == "test-project-api"
    assert p["display_name"] == "Test Project"
    assert p["git_repo_url"] == "https://github.com/test/test-repo.git"
    assert p["git_branch"] == "main"
    assert p["git_auth_username"] == "testuser"
    assert p["git_auth_token"] == "test-token-123"
    assert p["clone_path"] == "/tmp/test-clone"
    assert p["system_prompt"] == "You are a test assistant"
    assert p["fix_timeout_minutes"] == 60
    assert p["status"] == "active"
    assert "created_at" in p
    assert "updated_at" in p
    print(f"[PASS] Project detail matches created values")

    # Non-existent
    r2 = requests.get(f"{BASE_URL}/projects/99999", headers=headers())
    assert r2.json()["code"] != 0
    print(f"[PASS] Non-existent returns error")


def test_update_project():
    print("\n=== TEST: Update Project ===")
    if not TEST_IDS["project"]:
        print("[SKIP] No project to update")
        return
    pid = TEST_IDS["project"][0]
    update = {
        "display_name": "Updated Test Project",
        "description": "Updated description",
        "fix_timeout_minutes": 120,
        "status": "disabled"
    }
    r = requests.put(f"{BASE_URL}/projects/{pid}", json=update, headers=headers())
    assert r.status_code == 200
    data = r.json()
    assert data["code"] == 0
    assert data["message"] == "更新成功"
    print(f"[PASS] Update succeeded")

    # Verify
    r2 = requests.get(f"{BASE_URL}/projects/{pid}", headers=headers())
    p = r2.json()["data"]
    assert p["display_name"] == "Updated Test Project"
    assert p["description"] == "Updated description"
    assert p["fix_timeout_minutes"] == 120
    assert p["status"] == "disabled"
    print(f"[PASS] Update persisted")

    # Non-existent
    r3 = requests.put(f"{BASE_URL}/projects/99999", json={"display_name": "nope"}, headers=headers())
    assert r3.json()["code"] != 0
    print(f"[PASS] Update non-existent returns error")

    # Reset status
    requests.put(f"{BASE_URL}/projects/{pid}", json={"status": "active"}, headers=headers())


def test_delete_project():
    print("\n=== TEST: Delete Project ===")
    payload = {"name": "test-project-to-delete", "git_repo_url": "https://github.com/test/to-delete.git"}
    r = requests.post(f"{BASE_URL}/projects/", json=payload, headers=headers())
    pid = r.json()["data"]["id"]
    TEST_IDS["project"].append(pid)

    r2 = requests.delete(f"{BASE_URL}/projects/{pid}", headers=headers())
    assert r2.json()["code"] == 0
    print(f"[PASS] Delete succeeded")

    r3 = requests.get(f"{BASE_URL}/projects/{pid}", headers=headers())
    assert r3.json()["code"] != 0
    print(f"[PASS] Deleted project no longer accessible")

    r4 = requests.delete(f"{BASE_URL}/projects/99999", headers=headers())
    assert r4.json()["code"] != 0
    print(f"[PASS] Delete non-existent returns error")


# ========== CLAUDE SETTINGS TESTS ==========

def test_create_claude_settings():
    print("\n=== TEST: Create Claude Settings ===")
    payload = {
        "name": "test-settings-api",
        "display_name": "Test Settings",
        "description": "Test settings for API testing",
        "model": "claude-sonnet-4-6",
        "max_turns": 50,
        "permission_mode": "acceptEdits",
        "settings_json": json.dumps({"theme": "dark", "permissions": {"allow": ["*"]}})
    }
    r = requests.post(f"{BASE_URL}/claude-settings/", json=payload, headers=headers())
    assert r.status_code == 200
    data = r.json()
    assert data["code"] == 0
    assert "id" in data["data"]
    assert data["data"]["name"] == "test-settings-api"
    sid = data["data"]["id"]
    TEST_IDS["settings"].append(sid)
    print(f"[PASS] Created settings id={sid}")

    # Duplicate
    r2 = requests.post(f"{BASE_URL}/claude-settings/", json=payload, headers=headers())
    assert r2.json()["code"] != 0
    print(f"[PASS] Duplicate name rejected")

    # Invalid settings_json
    r3 = requests.post(f"{BASE_URL}/claude-settings/", json={"name": "test-settings-bad-json", "settings_json": "not json"}, headers=headers())
    assert r3.json()["code"] != 0
    print(f"[PASS] Invalid settings_json rejected")

    # Minimal creation
    r4 = requests.post(f"{BASE_URL}/claude-settings/", json={"name": "test-settings-minimal"}, headers=headers())
    assert r4.status_code == 200
    data4 = r4.json()
    assert data4["code"] == 0
    sid4 = data4["data"]["id"]
    TEST_IDS["settings"].append(sid4)
    print(f"[PASS] Created settings with defaults id={sid4}")


def test_list_claude_settings():
    print("\n=== TEST: List Claude Settings ===")
    r = requests.get(f"{BASE_URL}/claude-settings/", headers=headers())
    assert r.status_code == 200
    data = r.json()
    assert data["code"] == 0
    settings = data["data"]
    assert isinstance(settings, list)
    print(f"[PASS] List returned {len(settings)} settings")

    # Check settings_json NOT in list
    for s in settings:
        assert "settings_json" not in s, "settings_json exposed in list!"
    print(f"[PASS] No settings_json in list response")

    # Search
    r2 = requests.get(f"{BASE_URL}/claude-settings/?search=test-settings-api", headers=headers())
    data2 = r2.json()
    found = any("test-settings-api" in s.get("name", "") for s in data2["data"])
    assert found
    print(f"[PASS] Search works")


def test_get_claude_settings():
    print("\n=== TEST: Get Claude Settings Detail ===")
    if not TEST_IDS["settings"]:
        print("[SKIP] No settings to retrieve")
        return
    sid = TEST_IDS["settings"][0]
    r = requests.get(f"{BASE_URL}/claude-settings/{sid}", headers=headers())
    assert r.status_code == 200
    data = r.json()
    assert data["code"] == 0
    s = data["data"]
    assert s["name"] == "test-settings-api"
    assert s["display_name"] == "Test Settings"
    assert s["model"] == "claude-sonnet-4-6"
    assert s["max_turns"] == 50
    assert s["permission_mode"] == "acceptEdits"
    assert s["settings_json"] is not None
    assert s["status"] == "active"
    assert "created_at" in s
    assert "updated_at" in s
    print(f"[PASS] Settings detail matches")

    # Non-existent
    r2 = requests.get(f"{BASE_URL}/claude-settings/99999", headers=headers())
    assert r2.json()["code"] != 0
    print(f"[PASS] Non-existent returns error")


def test_update_claude_settings():
    print("\n=== TEST: Update Claude Settings ===")
    if not TEST_IDS["settings"]:
        print("[SKIP] No settings to update")
        return
    sid = TEST_IDS["settings"][0]
    update = {
        "display_name": "Updated Settings",
        "max_turns": 100,
        "permission_mode": "bypassPermissions",
        "status": "disabled"
    }
    r = requests.put(f"{BASE_URL}/claude-settings/{sid}", json=update, headers=headers())
    assert r.status_code == 200
    data = r.json()
    assert data["code"] == 0
    assert data["message"] == "更新成功"
    print(f"[PASS] Update succeeded")

    # Verify
    r2 = requests.get(f"{BASE_URL}/claude-settings/{sid}", headers=headers())
    s = r2.json()["data"]
    assert s["display_name"] == "Updated Settings"
    assert s["max_turns"] == 100
    assert s["permission_mode"] == "bypassPermissions"
    assert s["status"] == "disabled"
    print(f"[PASS] Update persisted")

    # Non-existent
    r3 = requests.put(f"{BASE_URL}/claude-settings/99999", json={"display_name": "nope"}, headers=headers())
    assert r3.json()["code"] != 0
    print(f"[PASS] Update non-existent returns error")


def test_delete_claude_settings():
    print("\n=== TEST: Delete Claude Settings ===")
    r = requests.post(f"{BASE_URL}/claude-settings/", json={"name": "test-settings-to-delete"}, headers=headers())
    sid = r.json()["data"]["id"]
    TEST_IDS["settings"].append(sid)

    r2 = requests.delete(f"{BASE_URL}/claude-settings/{sid}", headers=headers())
    assert r2.json()["code"] == 0
    print(f"[PASS] Delete succeeded")

    r3 = requests.get(f"{BASE_URL}/claude-settings/{sid}", headers=headers())
    assert r3.json()["code"] != 0
    print(f"[PASS] Deleted settings no longer accessible")

    r4 = requests.delete(f"{BASE_URL}/claude-settings/99999", headers=headers())
    assert r4.json()["code"] != 0
    print(f"[PASS] Delete non-existent returns error")


# ========== CONTRACT VALIDATION ==========

def contract_validation():
    print("\n=== CONTRACT VALIDATION ===")
    issues = []

    # Validate project list
    if TEST_IDS["project"]:
        r = requests.get(f"{BASE_URL}/projects/", headers=headers())
        projects = r.json()["data"]
        if projects:
            p = projects[0]
            list_fields = ["id", "name", "display_name", "description", "git_repo_url",
                          "git_branch", "clone_path", "status", "created_at"]
            for f in list_fields:
                if f not in p:
                    issues.append(f"[FAIL] Project List - Missing field '{f}'")
                elif f == "id" and not isinstance(p[f], int):
                    issues.append(f"[FAIL] Project List - 'id' type mismatch: expected int, got {type(p[f]).__name__}")
                elif f in ("name", "display_name", "description", "git_repo_url", "git_branch", "clone_path", "status") and not isinstance(p[f], (str, type(None))):
                    issues.append(f"[FAIL] Project List - '{f}' type mismatch: expected string, got {type(p[f]).__name__}")

            # Sensitive fields
            if "git_auth_token" in p:
                issues.append(f"[FAIL] Project List - 'git_auth_token' exposed! Must NOT be in list")
            if "git_auth_username" in p:
                issues.append(f"[FAIL] Project List - 'git_auth_username' exposed! Must NOT be in list")

    # Validate project detail
    if TEST_IDS["project"]:
        pid = TEST_IDS["project"][0]
        r = requests.get(f"{BASE_URL}/projects/{pid}", headers=headers())
        p = r.json()["data"]
        detail_fields = ["id", "name", "display_name", "description", "git_repo_url",
                        "git_branch", "git_auth_username", "git_auth_token", "clone_path",
                        "system_prompt", "fix_timeout_minutes", "status", "created_at", "updated_at"]
        for f in detail_fields:
            if f not in p:
                issues.append(f"[FAIL] Project Detail - Missing field '{f}'")
            elif f == "id" and not isinstance(p[f], int):
                issues.append(f"[FAIL] Project Detail - 'id' type mismatch: expected int, got {type(p[f]).__name__}")
            elif f == "fix_timeout_minutes" and not isinstance(p[f], int):
                issues.append(f"[FAIL] Project Detail - 'fix_timeout_minutes' type mismatch: expected int, got {type(p[f]).__name__}")

        # Status enum check
        if "status" in p and p["status"] not in ("active", "disabled"):
            issues.append(f"[FAIL] Project Detail - 'status' value '{p['status']}' not in valid enum values (active, disabled)")

    # Validate settings list
    if TEST_IDS["settings"]:
        r = requests.get(f"{BASE_URL}/claude-settings/", headers=headers())
        settings = r.json()["data"]
        if settings:
            s = settings[0]
            list_fields = ["id", "name", "display_name", "description", "model",
                          "max_turns", "permission_mode", "status", "created_at"]
            for f in list_fields:
                if f not in s:
                    issues.append(f"[FAIL] Settings List - Missing field '{f}'")
                elif f == "id" and not isinstance(s[f], int):
                    issues.append(f"[FAIL] Settings List - 'id' type mismatch")
                elif f == "max_turns" and not isinstance(s[f], int):
                    issues.append(f"[FAIL] Settings List - 'max_turns' type mismatch")

            if "settings_json" in s:
                issues.append(f"[FAIL] Settings List - 'settings_json' exposed! Must NOT be in list")

            if "permission_mode" in s:
                valid = ("default", "acceptEdits", "bypassPermissions", "plan")
                if s["permission_mode"] not in valid:
                    issues.append(f"[FAIL] Settings List - 'permission_mode'='{s['permission_mode']}' not valid")

    # Validate settings detail
    if TEST_IDS["settings"]:
        sid = TEST_IDS["settings"][0]
        r = requests.get(f"{BASE_URL}/claude-settings/{sid}", headers=headers())
        s = r.json()["data"]
        detail_fields = ["id", "name", "display_name", "description", "model",
                        "max_turns", "permission_mode", "settings_json", "status",
                        "created_at", "updated_at"]
        for f in detail_fields:
            if f not in s:
                issues.append(f"[FAIL] Settings Detail - Missing field '{f}'")
            elif f == "max_turns" and not isinstance(s[f], int):
                issues.append(f"[FAIL] Settings Detail - 'max_turns' type mismatch")

        if "permission_mode" in s:
            valid = ("default", "acceptEdits", "bypassPermissions", "plan")
            if s["permission_mode"] not in valid:
                issues.append(f"[FAIL] Settings Detail - 'permission_mode'='{s['permission_mode']}' not valid")

    if issues:
        print("\n--- Contract Issues Found ---")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("[PASS] All contract validations passed!")

    return issues


def cleanup():
    print("\n=== CLEANUP ===")
    for sid in reversed(TEST_IDS["settings"]):
        try:
            r = requests.delete(f"{BASE_URL}/claude-settings/{sid}", headers=headers())
            if r.json()["code"] == 0:
                print(f"[CLEANUP] Deleted settings id={sid}")
        except Exception as e:
            print(f"[CLEANUP] Error: {e}")
    for pid in reversed(TEST_IDS["project"]):
        try:
            r = requests.delete(f"{BASE_URL}/projects/{pid}", headers=headers())
            if r.json()["code"] == 0:
                print(f"[CLEANUP] Deleted project id={pid}")
        except Exception as e:
            print(f"[CLEANUP] Error: {e}")


if __name__ == "__main__":
    failures = 0
    try:
        login()
        test_create_project()
        test_list_projects()
        test_get_project()
        test_update_project()
        test_delete_project()
        test_create_claude_settings()
        test_list_claude_settings()
        test_get_claude_settings()
        test_update_claude_settings()
        test_delete_claude_settings()
        issues = contract_validation()

        if issues:
            failures = len(issues)

        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print(f"[PASS] All functional tests completed (10 test suites)")
        print(f"[CONTRACT] Issues found: {len(issues)}")

    except AssertionError as e:
        print(f"\n[FAIL] {e}")
        failures += 1
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        failures += 1
    finally:
        cleanup()
        print("\nDone.")
        sys.exit(1 if failures > 0 else 0)
