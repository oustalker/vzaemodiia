"""Наскрізний тест основних сценаріїв. python smoke_test.py"""
from __future__ import annotations

import asyncio

import httpx

from app.main import app

PASSWORD = "demo1234"
ok_count = 0
fail_count = 0


def check(label: str, condition: bool, extra: str = "") -> None:
    global ok_count, fail_count
    if condition:
        ok_count += 1
        print(f"  OK   {label}")
    else:
        fail_count += 1
        print(f"  FAIL {label} {extra}")


async def login(client: httpx.AsyncClient, username: str) -> dict:
    r = await client.post("/api/auth/login", json={"username": username, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def main() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        print("\n[авторизація]")
        r = await c.get("/api/health")
        check("health", r.status_code == 200)

        r = await c.post("/api/auth/login", json={"username": "kovalenko", "password": "wrong"})
        check("невірний пароль -> 401", r.status_code == 401)

        r = await c.get("/api/needs")
        check("без токена -> 401", r.status_code == 401)

        mil = await login(c, "kovalenko")
        vol = await login(c, "marchenko")
        vol2 = await login(c, "bondar")
        civ = await login(c, "lysenko")

        r = await c.post("/api/auth/register", json={
            "username": "kovalenko", "password": "abcdef", "first_name": "X",
            "last_name": "Y", "role": "military"})
        check("дубль логіна -> 409", r.status_code == 409)

        print("\n[довідники та дошка]")
        r = await c.get("/api/meta")
        check("meta", r.status_code == 200 and "categories" in r.json())

        r = await c.get("/api/needs", headers=vol)
        board = r.json()
        check("дошка не порожня", len(board) > 0, str(len(board)))
        check("критичні зверху", board[0]["urgency"] == "critical", board[0]["urgency"])

        r = await c.get("/api/needs?category=medical", headers=vol)
        check("фільтр за категорією", all(n["category"] == "medical" for n in r.json()))

        r = await c.get("/api/needs?q=генератор", headers=vol)
        check("пошук", len(r.json()) >= 1, str(len(r.json())))

        print("\n[права ролей]")
        payload = {"title": "Тестовий запит", "description": "Опис тестового запиту",
                   "category": "gear", "urgency": "normal", "quantity": 3, "unit": "шт"}
        r = await c.post("/api/needs", json=payload, headers=vol)
        check("волонтер не створює запит -> 403", r.status_code == 403, r.text[:80])

        r = await c.post("/api/needs", json=payload, headers=mil)
        check("військовий створює запит -> 201", r.status_code == 201, r.text[:120])
        need_id = r.json()["id"]

        print("\n[життєвий цикл запиту]")
        r = await c.post(f"/api/needs/{need_id}/take", headers=civ)
        check("цивільний не бере в роботу -> 403", r.status_code == 403)

        r = await c.post(f"/api/needs/{need_id}/take", headers=vol)
        check("волонтер бере в роботу", r.status_code == 200 and r.json()["status"] == "in_progress")

        r = await c.post(f"/api/needs/{need_id}/take", headers=vol2)
        check("другий волонтер не перехопить -> 409", r.status_code == 409)

        r = await c.post(f"/api/needs/{need_id}/confirm", json={}, headers=mil)
        check("не можна підтвердити з in_progress -> 409", r.status_code == 409)

        r = await c.post(f"/api/needs/{need_id}/submit", json={"comment": "Передав"}, headers=vol2)
        check("чужий волонтер не здає роботу -> 403", r.status_code == 403)

        r = await c.post(f"/api/needs/{need_id}/submit", json={"comment": "Передав"}, headers=vol)
        check("волонтер здає роботу", r.json().get("status") == "pending", r.text[:80])

        r = await c.post(f"/api/needs/{need_id}/reject", json={"comment": "Не те"}, headers=mil)
        check("автор відхиляє -> назад в роботу", r.json().get("status") == "in_progress")

        await c.post(f"/api/needs/{need_id}/submit", json={}, headers=vol)
        r = await c.post(f"/api/needs/{need_id}/confirm", json={}, headers=vol)
        check("не автор не підтверджує -> 403", r.status_code == 403)

        r = await c.post(f"/api/needs/{need_id}/confirm", json={}, headers=mil)
        check("автор підтверджує", r.json().get("status") == "completed")

        r = await c.post(f"/api/needs/{need_id}/take", headers=vol)
        check("завершений запит не взяти -> 409", r.status_code == 409)

        r = await c.get(f"/api/needs/{need_id}", headers=vol)
        history = r.json()["history"]
        check("історія записана", len(history) >= 6, str([h["kind"] for h in history]))

        print("\n[збори]")
        r = await c.post("/api/funds", json={
            "title": "Тестовий збір", "description": "Опис збору",
            "target_amount": 1000, "requisites": "test"}, headers=vol)
        check("волонтер створює збір -> 201", r.status_code == 201, r.text[:100])
        fund_id = r.json()["id"]

        r = await c.post("/api/funds", json={
            "title": "Не можна", "description": "Опис", "target_amount": 100}, headers=civ)
        check("цивільний не створює збір -> 403", r.status_code == 403)

        r = await c.post(f"/api/funds/{fund_id}/contribute", json={"amount": 400}, headers=civ)
        check("внесок рухає суму", r.json().get("current_amount") == 400, r.text[:100])

        r = await c.post(f"/api/funds/{fund_id}/contribute", json={"amount": 700}, headers=mil)
        body = r.json()
        check("збір закривається на цілі",
              body.get("current_amount") == 1100 and body.get("status") == "closed", r.text[:100])

        r = await c.post(f"/api/funds/{fund_id}/contribute", json={"amount": 10}, headers=civ)
        check("у закритий збір не внести -> 409", r.status_code == 409)

        r = await c.post(f"/api/funds/{fund_id}/contribute", json={"amount": -5}, headers=civ)
        check("відʼємна сума -> 422", r.status_code == 422)

        r = await c.get(f"/api/funds/{fund_id}", headers=civ)
        check("список внесків", len(r.json()["contributions"]) == 2)

        print("\n[донати речами]")
        r = await c.post("/api/donations", json={
            "item": "Тестова позиція", "quantity": 5, "unit": "шт",
            "category": "gear", "contact": "@test"}, headers=civ)
        check("цивільний розміщує донат -> 201", r.status_code == 201, r.text[:100])
        donation_id = r.json()["id"]

        r = await c.get("/api/needs?scope=all", headers=civ)
        open_need = next(n["id"] for n in r.json() if n["status"] == "open")

        r = await c.post(f"/api/donations/{donation_id}/link/{open_need}", headers=vol)
        check("чужий донат не привʼязати -> 403", r.status_code == 403)

        r = await c.post(f"/api/donations/{donation_id}/link/{open_need}", headers=civ)
        check("привʼязка до запиту", r.json().get("status") == "reserved", r.text[:100])

        r = await c.post(f"/api/donations/{donation_id}/status",
                         json={"status": "delivered"}, headers=civ)
        check("позначено переданим", r.json().get("status") == "delivered")

        print("\n[зведення, стрічка, профілі]")
        r = await c.get("/api/stats/overview", headers=vol)
        ov = r.json()
        check("зведення", ov["needs_open"] > 0 and ov["funds_raised"] > 0, str(ov)[:120])

        r = await c.get("/api/stats/leaderboard", headers=vol)
        lb = r.json()
        check("дошка пошани", len(lb) > 0 and lb[0]["completed"] >= lb[-1]["completed"])

        r = await c.get("/api/feed?limit=20", headers=vol)
        check("стрічка", len(r.json()) == 20)

        r = await c.get("/api/users/marchenko", headers=civ)
        check("чужий профіль зі статистикою",
              r.json()["stats"]["needs_completed"] >= 1, str(r.json()["stats"]))

        r = await c.patch("/api/auth/me", json={"about": "Тест про себе"}, headers=vol)
        check("редагування профілю", r.json()["about"] == "Тест про себе")

        r = await c.get("/api/needs/nonexistent", headers=vol)
        check("невідомий id -> 404", r.status_code == 404)

    print(f"\n=== пройдено {ok_count}, провалено {fail_count} ===")
    raise SystemExit(1 if fail_count else 0)


if __name__ == "__main__":
    asyncio.run(main())
