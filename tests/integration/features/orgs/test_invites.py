import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.uow import AppUnitOfWork
from app.features.orgs.service import OrgService
from app.shared.exceptions import ConflictException


async def _register(client: AsyncClient, email: str, full_name: str) -> dict:
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123",
            "full_name": full_name,
            "consent_to_processing": True,
        },
    )
    assert reg.status_code == 201, reg.text
    return reg.json()


async def _create_org(client: AsyncClient, token: str, name: str) -> dict:
    resp = await client.post(
        "/api/v1/orgs",
        json={"name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_invite(
    client: AsyncClient, token: str, org_id: str, email: str
) -> dict:
    resp = await client.post(
        f"/api/v1/orgs/{org_id}/invites",
        json={"email": email},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestInviteFullCycle:
    async def test_bob_invites_alice_full_cycle(self, client):
        bob = await _register(client, "bob@test.com", "Bob Baker")
        alice = await _register(client, "alice@test.com", "Alice Baker")
        bob_token = bob["access_token"]
        alice_token = alice["access_token"]

        org = await _create_org(client, bob_token, "Bob's Bakery")
        org_id = org["id"]

        invite = await _create_invite(client, bob_token, org_id, "alice@test.com")
        assert invite["invite_id"]
        assert len(invite["token"]) > 20
        assert invite["expires_at"] is not None

        accept = await client.post(
            "/api/v1/auth/invites/accept",
            json={"token": invite["token"]},
            headers=_auth(alice_token),
        )
        assert accept.status_code == 200, accept.text
        accepted = accept.json()
        assert accepted["org_id"] == org_id
        assert accepted["org_name"] == "Bob's Bakery"
        assert accepted["role"] == "member"

        # Both see the org in GET /orgs
        for tok in (bob_token, alice_token):
            orgs = (await client.get("/api/v1/orgs", headers=_auth(tok))).json()
            assert any(o["id"] == org_id for o in orgs)

        # Bob sees alice in members with role=member
        members = (
            await client.get(f"/api/v1/orgs/{org_id}/members", headers=_auth(bob_token))
        ).json()
        assert len(members) == 2
        by_email = {m["email"]: m for m in members}
        assert by_email["bob@test.com"]["role"] == "owner"
        assert by_email["alice@test.com"]["role"] == "member"
        assert by_email["alice@test.com"]["full_name"] == "Alice Baker"
        assert by_email["alice@test.com"]["user_id"] == alice["user"]["id"]

    async def test_owner_role_set_on_org_creation(self, client):
        user = await _register(client, "owner1@test.com", "Owner One")
        token = user["access_token"]
        org = await _create_org(client, token, "Single Owner Org")

        members = (
            await client.get(f"/api/v1/orgs/{org['id']}/members", headers=_auth(token))
        ).json()
        assert len(members) == 1
        assert members[0]["role"] == "owner"
        assert members[0]["user_id"] == user["user"]["id"]

    async def test_accept_requires_authentication(self, client):
        bob = await _register(client, "bob2@test.com", "Bob Two")
        org = await _create_org(client, bob["access_token"], "Org2")
        invite = await _create_invite(
            client, bob["access_token"], org["id"], "someone@test.com"
        )
        # Register set auth cookies on the shared client: cookie-authenticated
        # bob's email doesn't match the invite -> 403; truly anonymous -> 401.
        resp_member = await client.post(
            "/api/v1/auth/invites/accept", json={"token": invite["token"]}
        )
        assert resp_member.status_code == 403

        client.cookies.clear()
        resp_anon = await client.post(
            "/api/v1/auth/invites/accept", json={"token": invite["token"]}
        )
        assert resp_anon.status_code == 401

    async def test_accept_unknown_token_404(self, client):
        user = await _register(client, "unknown-tok@test.com", "U T")
        resp = await client.post(
            "/api/v1/auth/invites/accept",
            json={"token": "no-such-token"},
            headers=_auth(user["access_token"]),
        )
        assert resp.status_code == 404


class TestInviteExpiryAndReuse:
    async def test_expired_invite_returns_410(self, client, test_session_factory):
        bob = await _register(client, "bob3@test.com", "Bob Three")
        alice = await _register(client, "alice3@test.com", "Alice Three")
        org = await _create_org(client, bob["access_token"], "Org3")
        invite = await _create_invite(
            client, bob["access_token"], org["id"], "alice3@test.com"
        )

        # Forge expiry in the past directly via DB
        async with test_session_factory() as session:
            await session.execute(
                text("UPDATE invites SET expires_at = now() - interval '1 day'")
            )
            await session.commit()

        resp = await client.post(
            "/api/v1/auth/invites/accept",
            json={"token": invite["token"]},
            headers=_auth(alice["access_token"]),
        )
        assert resp.status_code == 410

    async def test_repeat_accept_returns_409(self, client):
        bob = await _register(client, "bob4@test.com", "Bob Four")
        alice = await _register(client, "alice4@test.com", "Alice Four")
        org = await _create_org(client, bob["access_token"], "Org4")
        invite = await _create_invite(
            client, bob["access_token"], org["id"], "alice4@test.com"
        )

        first = await client.post(
            "/api/v1/auth/invites/accept",
            json={"token": invite["token"]},
            headers=_auth(alice["access_token"]),
        )
        assert first.status_code == 200

        second = await client.post(
            "/api/v1/auth/invites/accept",
            json={"token": invite["token"]},
            headers=_auth(alice["access_token"]),
        )
        assert second.status_code == 409

    async def test_used_invite_not_listed_as_active(self, client):
        bob = await _register(client, "bob5@test.com", "Bob Five")
        alice = await _register(client, "alice5@test.com", "Alice Five")
        bob_token = bob["access_token"]
        org = await _create_org(client, bob_token, "Org5")
        invite = await _create_invite(client, bob_token, org["id"], "alice5@test.com")

        await client.post(
            "/api/v1/auth/invites/accept",
            json={"token": invite["token"]},
            headers=_auth(alice["access_token"]),
        )

        listed = (
            await client.get(
                f"/api/v1/orgs/{org['id']}/invites", headers=_auth(bob_token)
            )
        ).json()
        assert listed == []


class TestInvitePermissions:
    async def test_non_member_cannot_create_invite(self, client):
        bob = await _register(client, "bob6@test.com", "Bob Six")
        outsider = await _register(client, "outsider@test.com", "Out Sider")
        org = await _create_org(client, bob["access_token"], "Org6")

        resp = await client.post(
            f"/api/v1/orgs/{org['id']}/invites",
            json={"email": "newbie@test.com"},
            headers=_auth(outsider["access_token"]),
        )
        assert resp.status_code == 403

    async def test_member_without_owner_role_cannot_create_invite(self, client):
        bob = await _register(client, "bob7@test.com", "Bob Seven")
        alice = await _register(client, "alice7@test.com", "Alice Seven")
        bob_token = bob["access_token"]
        org = await _create_org(client, bob_token, "Org7")
        invite = await _create_invite(client, bob_token, org["id"], "alice7@test.com")
        acc = await client.post(
            "/api/v1/auth/invites/accept",
            json={"token": invite["token"]},
            headers=_auth(alice["access_token"]),
        )
        assert acc.status_code == 200

        resp = await client.post(
            f"/api/v1/orgs/{org['id']}/invites",
            json={"email": "someoneelse@test.com"},
            headers=_auth(alice["access_token"]),
        )
        assert resp.status_code == 403

    async def test_member_cannot_list_invites(self, client):
        bob = await _register(client, "bob8@test.com", "Bob Eight")
        alice = await _register(client, "alice8@test.com", "Alice Eight")
        bob_token = bob["access_token"]
        org = await _create_org(client, bob_token, "Org8")
        invite = await _create_invite(client, bob_token, org["id"], "alice8@test.com")
        await client.post(
            "/api/v1/auth/invites/accept",
            json={"token": invite["token"]},
            headers=_auth(alice["access_token"]),
        )

        resp = await client.get(
            f"/api/v1/orgs/{org['id']}/invites", headers=_auth(alice["access_token"])
        )
        assert resp.status_code == 403

    async def test_owner_lists_active_invites_and_revokes(self, client):
        bob = await _register(client, "bob9@test.com", "Bob Nine")
        bob_token = bob["access_token"]
        org = await _create_org(client, bob_token, "Org9")
        inv1 = await _create_invite(client, bob_token, org["id"], "a9@test.com")
        await _create_invite(client, bob_token, org["id"], "b9@test.com")

        listed = (
            await client.get(
                f"/api/v1/orgs/{org['id']}/invites", headers=_auth(bob_token)
            )
        ).json()
        assert len(listed) == 2
        emails = {i["email"] for i in listed}
        assert emails == {"a9@test.com", "b9@test.com"}
        assert all("token" in i and "expires_at" in i for i in listed)

        # Duplicate active invite for same email -> 409
        dup = await client.post(
            f"/api/v1/orgs/{org['id']}/invites",
            json={"email": "a9@test.com"},
            headers=_auth(bob_token),
        )
        assert dup.status_code == 409

        # Revoke -> 204, then list shows one; unknown id -> 404
        del_resp = await client.delete(
            f"/api/v1/orgs/{org['id']}/invites/{inv1['invite_id']}",
            headers=_auth(bob_token),
        )
        assert del_resp.status_code == 204
        listed_after = (
            await client.get(
                f"/api/v1/orgs/{org['id']}/invites", headers=_auth(bob_token)
            )
        ).json()
        assert [i["email"] for i in listed_after] == ["b9@test.com"]

        del_missing = await client.delete(
            f"/api/v1/orgs/{org['id']}/invites/00000000-0000-0000-0000-000000000000",
            headers=_auth(bob_token),
        )
        assert del_missing.status_code == 404

    async def test_legacy_owner_can_create_invite(self, client, test_session_factory):
        """The organization owner remains an owner after the role migration."""
        bob = await _register(client, "legacy-owner@test.com", "Legacy Owner")
        org = await _create_org(client, bob["access_token"], "Legacy Owner Org")

        # Reproduce a pre-role-migration organization: the new column's
        # default was `member`, while organizations.owner_id stayed correct.
        async with test_session_factory() as session:
            await session.execute(
                text(
                    "UPDATE user_orgs SET role = 'member' "
                    "WHERE user_id = CAST(:user_id AS uuid) "
                    "AND org_id = CAST(:org_id AS uuid)"
                ),
                {"user_id": bob["user"]["id"], "org_id": org["id"]},
            )
            await session.commit()

        invite = await _create_invite(
            client, bob["access_token"], org["id"], "new-member@test.com"
        )
        assert invite["invite_id"]

        members = (
            await client.get(
                f"/api/v1/orgs/{org['id']}/members",
                headers=_auth(bob["access_token"]),
            )
        ).json()
        assert members[0]["role"] == "owner"

    async def test_invalid_email_rejected(self, client):
        bob = await _register(client, "bob10@test.com", "Bob Ten")
        org = await _create_org(client, bob["access_token"], "Org10")
        resp = await client.post(
            f"/api/v1/orgs/{org['id']}/invites",
            json={"email": "not-an-email"},
            headers=_auth(bob["access_token"]),
        )
        assert resp.status_code == 422

    async def test_wrong_email_cannot_accept_invite(self, client):
        bob = await _register(client, "bob-wrong@test.com", "Bob Wrong")
        alice = await _register(client, "alice-wrong@test.com", "Alice Wrong")
        org = await _create_org(client, bob["access_token"], "OrgWrong")

        invite = await _create_invite(
            client, bob["access_token"], org["id"], "sovwva7@gmail.com"
        )

        # Alice tries to accept an invite meant for sovwva7@gmail.com
        resp = await client.post(
            "/api/v1/auth/invites/accept",
            json={"token": invite["token"]},
            headers=_auth(alice["access_token"]),
        )
        assert resp.status_code == 403
        assert (
            resp.json()["detail"]
            == "This invitation was sent to a different email address"
        )


class TestMemberRemoval:
    async def test_owner_removes_member(self, client):
        bob = await _register(client, "bob11@test.com", "Bob Eleven")
        alice = await _register(client, "alice11@test.com", "Alice Eleven")
        bob_token = bob["access_token"]
        alice_token = alice["access_token"]
        org = await _create_org(client, bob_token, "Org11")
        invite = await _create_invite(client, bob_token, org["id"], "alice11@test.com")
        await client.post(
            "/api/v1/auth/invites/accept",
            json={"token": invite["token"]},
            headers=_auth(alice_token),
        )
        alice_id = alice["user"]["id"]

        resp = await client.delete(
            f"/api/v1/orgs/{org['id']}/members/{alice_id}", headers=_auth(bob_token)
        )
        assert resp.status_code == 204

        members = (
            await client.get(
                f"/api/v1/orgs/{org['id']}/members", headers=_auth(bob_token)
            )
        ).json()
        assert [m["email"] for m in members] == ["bob11@test.com"]

        orgs = (await client.get("/api/v1/orgs", headers=_auth(alice_token))).json()
        assert not any(o["id"] == org["id"] for o in orgs)

    async def test_remove_missing_member_404(self, client):
        bob = await _register(client, "bob12@test.com", "Bob Twelve")
        org = await _create_org(client, bob["access_token"], "Org12")
        stranger = await _register(client, "stranger12@test.com", "Stranger")
        resp = await client.delete(
            f"/api/v1/orgs/{org['id']}/members/{stranger['user']['id']}",
            headers=_auth(bob["access_token"]),
        )
        assert resp.status_code == 404

    async def test_self_removal_forbidden(self, client):
        bob = await _register(client, "bob13@test.com", "Bob Thirteen")
        bob_token = bob["access_token"]
        org = await _create_org(client, bob_token, "Org13")

        resp = await client.delete(
            f"/api/v1/orgs/{org['id']}/members/{bob['user']['id']}",
            headers=_auth(bob_token),
        )
        assert resp.status_code == 403

        # Still a member
        members = (
            await client.get(
                f"/api/v1/orgs/{org['id']}/members", headers=_auth(bob_token)
            )
        ).json()
        assert len(members) == 1

    async def test_last_owner_not_removable_via_service(
        self, client, test_session_factory
    ):
        """Defense-in-depth guard: even if actor is owner and target is the last
        remaining owner (crafted state where actor was demoted), removal is blocked."""
        bob = await _register(client, "bob14@test.com", "Bob Fourteen")
        alice = await _register(client, "alice14@test.com", "Alice Fourteen")
        org = await _create_org(client, bob["access_token"], "Org14")
        invite = await _create_invite(
            client, bob["access_token"], org["id"], "alice14@test.com"
        )
        await client.post(
            "/api/v1/auth/invites/accept",
            json={"token": invite["token"]},
            headers=_auth(alice["access_token"]),
        )

        # Craft: promote alice to owner, demote bob to member -> alice is the
        # last owner. Bob (actor, still allowed through service directly)
        # tries to remove her — the last-owner guard must refuse.
        async with test_session_factory() as session:
            await session.execute(
                text(
                    "UPDATE user_orgs uo SET role = 'owner' "
                    "FROM users u "
                    "WHERE uo.user_id = u.id AND u.email = 'alice14@test.com'"
                )
            )
            await session.execute(
                text(
                    "UPDATE user_orgs uo SET role = 'member' "
                    "FROM users u "
                    "WHERE uo.user_id = u.id AND u.email = 'bob14@test.com'"
                )
            )
            await session.commit()

        uow = AppUnitOfWork(test_session_factory)
        service = OrgService(uow)
        with pytest.raises(ConflictException):
            await service.remove_member(
                org["id"], alice["user"]["id"], bob["user"]["id"]
            )
