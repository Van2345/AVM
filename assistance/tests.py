import json

from django.test import Client, TestCase
from django.utils import timezone

from .models import AssistanceRequest, Assignment, User, Volunteer


class ApplicationTests(TestCase):
    def create_user(self, username, role):
        return User.objects.create_user(
            username=username,
            password="Test-password-456",
            full_name=username.title(),
            role=role,
        )

    def post_json(self, client, path, data):
        return client.post(
            path,
            data=json.dumps(data),
            content_type="application/json",
        )

    def test_home_renders_django_template_and_csrf_token(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="app-data"')
        self.assertContains(response, 'src="/static/app.js"')
        self.assertIn("csrftoken", self.client.cookies)

    def test_requester_home_hides_admin_sections(self):
        requester = self.create_user("requester", User.Role.REQUESTER)
        self.client.force_login(requester)
        response = self.client.get("/")
        self.assertContains(response, "Request Help")
        self.assertNotContains(response, 'id="m_manage"')
        self.assertNotContains(response, 'id="p_manage"')
        self.assertNotContains(response, "Add volunteer")

    def test_public_registration_creates_requester(self):
        response = self.post_json(
            self.client,
            "/api/auth/register/",
            {
                "username": "new.requester",
                "full_name": "New Requester",
                "email": "requester@example.com",
                "password": "A-strong-password-987",
                "confirm": "A-strong-password-987",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            User.objects.get(username="new.requester").role, User.Role.REQUESTER
        )

    def test_requester_cannot_list_other_requesters(self):
        requester = self.create_user("requester", User.Role.REQUESTER)
        other = self.create_user("other", User.Role.REQUESTER)
        AssistanceRequest.objects.create(
            user=other,
            requester_name="Other Requester",
            contact="09171234567",
            assistance_type="Medical Assistance",
            location="Campus Gate",
            description="Needs help at the campus gate.",
            urgency=AssistanceRequest.Urgency.HIGH,
            needed_at=timezone.now(),
        )
        self.client.force_login(requester)
        response = self.client.get("/api/requests/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["requests"], [])

    def test_map_endpoint_does_not_return_requester_private_data(self):
        requester = self.create_user("requester", User.Role.REQUESTER)
        AssistanceRequest.objects.create(
            user=requester,
            request_code="REQ-000001",
            requester_name="Private Requester",
            contact="09171234567",
            assistance_type="Medical Assistance",
            location="Campus Gate",
            description="Private description.",
            urgency=AssistanceRequest.Urgency.HIGH,
            needed_at=timezone.now(),
        )
        self.client.force_login(requester)
        response = self.client.get("/api/requests/?map=1")
        item = response.json()["requests"][0]
        self.assertEqual(
            set(item),
            {
                "id",
                "request_code",
                "assistance_type",
                "status",
                "urgency",
                "location",
                "latitude",
                "longitude",
            },
        )

    def test_admin_can_assign_and_complete_request(self):
        admin = self.create_user("admin", User.Role.ADMIN)
        volunteer_user = self.create_user("volunteer", User.Role.VOLUNTEER)
        volunteer = Volunteer.objects.create(
            user=volunteer_user,
            volunteer_code="V-0001",
            full_name="Test Volunteer",
            contact="09171234567",
            skill="First aid",
            availability="Weekdays",
        )
        item = AssistanceRequest.objects.create(
            requester_name="Test Requester",
            contact="09181234567",
            assistance_type="Medical Assistance",
            location="Campus Gate",
            description="Needs help at the campus gate.",
            urgency=AssistanceRequest.Urgency.HIGH,
            needed_at=timezone.now(),
            request_code="REQ-000001",
        )
        self.client.force_login(admin)
        approved = self.post_json(
            self.client, "/api/requests/update/", {"id": item.pk, "action": "approve"}
        )
        self.assertTrue(approved.json()["success"])
        assigned = self.post_json(
            self.client,
            "/api/requests/update/",
            {"id": item.pk, "action": "assign", "volunteer_id": volunteer.pk},
        )
        self.assertTrue(assigned.json()["success"])
        self.assertEqual(
            Volunteer.objects.get(pk=volunteer.pk).status, Volunteer.Status.BUSY
        )
        started = self.post_json(
            self.client, "/api/requests/update/", {"id": item.pk, "action": "start"}
        )
        self.assertTrue(started.json()["success"])
        completed = self.post_json(
            self.client, "/api/requests/update/", {"id": item.pk, "action": "complete"}
        )
        self.assertTrue(completed.json()["success"])
        item.refresh_from_db()
        self.assertEqual(item.status, AssistanceRequest.Status.DONE)
        self.assertEqual(
            Assignment.objects.get(request=item).status, Assignment.Status.COMPLETED
        )
        self.assertEqual(
            Volunteer.objects.get(pk=volunteer.pk).status, Volunteer.Status.AVAILABLE
        )

    def test_csrf_protection_rejects_write_without_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        response = self.post_json(
            csrf_client,
            "/api/auth/register/",
            {
                "username": "new.requester",
                "full_name": "New Requester",
                "password": "A-strong-password-987",
                "confirm": "A-strong-password-987",
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_csrf_token_header_allows_write(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.get("/")
        response = csrf_client.post(
            "/api/auth/register/",
            data=json.dumps(
                {
                    "username": "csrf.user",
                    "full_name": "CSRF User",
                    "password": "A-strong-password-987",
                    "confirm": "A-strong-password-987",
                }
            ),
            content_type="application/json",
            HTTP_X_CSRF_TOKEN=csrf_client.cookies["csrftoken"].value,
        )
        self.assertEqual(response.status_code, 200)

    def test_superuser_is_created_with_admin_role(self):
        admin = User.objects.create_superuser(
            username="superuser",
            password="Test-password-456",
            full_name="System Administrator",
        )
        self.assertEqual(admin.role, User.Role.ADMIN)
        self.client.force_login(admin)
        response = self.client.get("/django-admin/assistance/user/add/")
        self.assertEqual(response.status_code, 200)
