import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import render
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_http_methods

from .models import ActivityLog, AssistanceRequest, Assignment, User, Volunteer

ASSISTANCE_TYPES = (
    "Medical Assistance",
    "Emergency Assistance",
    "Transportation",
    "Campus Assistance",
    "Lost and Found",
    "Other",
)
REQUEST_STATUSES = tuple(AssistanceRequest.Status.values)
URGENCY_LEVELS = tuple(AssistanceRequest.Urgency.values)
VOLUNTEER_STATUSES = tuple(Volunteer.Status.values)
CONTACT_PATTERN = re.compile(r"^[0-9+\-\s()]{7,20}$")
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.]{4,30}$")


def response_error(message, status=400):
    return JsonResponse({"success": False, "message": message}, status=status)


def response_ok(message, **extra):
    return JsonResponse({"success": True, "message": message, **extra})


def parse_body(request):
    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def actor_or_error(request, *roles):
    user = request.user
    if not user.is_authenticated or not user.is_active:
        return response_error("Please log in first.", 401)
    if roles and user.role not in roles:
        return response_error("You do not have permission to do this.", 403)
    return user


def log_activity(action, details, user=None, assistance_request=None):
    ActivityLog.objects.create(
        user=user,
        request=assistance_request,
        action=action,
        details=str(details)[:255],
    )


def normalized(value):
    return " ".join(str(value or "").split())


def parse_coordinates(data):
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    if latitude in (None, "") and longitude in (None, ""):
        return None, None, None
    try:
        lat = Decimal(str(latitude))
        lng = Decimal(str(longitude))
    except (InvalidOperation, TypeError, ValueError):
        return None, None, "Invalid map coordinates."
    if not lat.is_finite() or not lng.is_finite():
        return None, None, "Invalid map coordinates."
    if lat < -90 or lat > 90 or lng < -180 or lng > 180:
        return None, None, "Invalid map coordinates."
    try:
        return (
            lat.quantize(Decimal("0.000001")),
            lng.quantize(Decimal("0.000001")),
            None,
        )
    except InvalidOperation:
        return None, None, "Invalid map coordinates."


def validate_volunteer_data(data):
    name = normalized(data.get("full_name"))
    contact = str(data.get("contact") or "").strip()
    skill = normalized(data.get("skill"))
    availability = normalized(data.get("availability"))
    status = str(data.get("status") or "AVAILABLE").strip().upper()

    if not name or not contact or not skill or not availability:
        return None, "Please complete all required fields."
    if not 2 <= len(name) <= 100:
        return None, "Full name must be 2 to 100 characters."
    if not CONTACT_PATTERN.fullmatch(contact):
        return None, "Please enter a valid contact number."
    if len(skill) > 80:
        return None, "Skill / Role is too long (80 characters maximum)."
    if len(availability) > 100:
        return None, "Availability is too long (100 characters maximum)."
    if status not in VOLUNTEER_STATUSES:
        return None, "Invalid volunteer status."
    latitude, longitude, error = parse_coordinates(data)
    if error:
        return None, error
    return {
        "name": name,
        "contact": contact,
        "skill": skill,
        "availability": availability,
        "status": status,
        "latitude": latitude,
        "longitude": longitude,
    }, None


def serialize_request(item, assignment=None):
    volunteer = assignment.volunteer if assignment else None
    result = {
        "id": item.pk,
        "request_code": item.request_code,
        "user_id": item.user_id,
        "requester_name": item.requester_name,
        "contact": item.contact,
        "assistance_type": item.assistance_type,
        "location": item.location,
        "latitude": float(item.latitude) if item.latitude is not None else None,
        "longitude": float(item.longitude) if item.longitude is not None else None,
        "description": item.description,
        "urgency": item.urgency,
        "needed_at": item.needed_at.isoformat(),
        "status": item.status,
        "created_at": item.created_at.isoformat(),
        "volunteer_id": volunteer.pk if volunteer else None,
        "volunteer_code": volunteer.volunteer_code if volunteer else None,
        "volunteer_name": volunteer.full_name if volunteer else None,
    }
    return result


def serialize_volunteer(item, current_request=None):
    return {
        "id": item.pk,
        "volunteer_code": item.volunteer_code,
        "user_id": item.user_id,
        "full_name": item.full_name,
        "contact": item.contact,
        "skill": item.skill,
        "availability": item.availability,
        "status": item.status,
        "latitude": float(item.latitude) if item.latitude is not None else None,
        "longitude": float(item.longitude) if item.longitude is not None else None,
        "location_accuracy": (
            float(item.location_accuracy) if item.location_accuracy is not None else None
        ),
        "location_updated_at": (
            item.location_updated_at.isoformat() if item.location_updated_at else None
        ),
        "username": item.user.username if item.user_id else None,
        "current_request": current_request,
    }


@require_http_methods(["GET"])
def home(request):
    user = request.user if request.user.is_authenticated and request.user.is_active else None
    role = user.role if user else ""
    menu = [{"key": "dash", "label": "Dashboard", "icon": "dash"},
            {"key": "mapview", "label": "Live Map", "icon": "mapview"}]
    if role in (User.Role.ADMIN, User.Role.REQUESTER):
        menu.append({"key": "request", "label": "Request Help", "icon": "request"})
    if role == User.Role.ADMIN:
        menu.extend(
            [
                {"key": "volunteer", "label": "Volunteers", "icon": "volunteer"},
                {"key": "manage", "label": "Manage", "icon": "manage"},
            ]
        )
    titles = {
        User.Role.ADMIN: "Admin Dashboard",
        User.Role.VOLUNTEER: "Volunteer Dashboard",
        User.Role.REQUESTER: "Requester Dashboard",
    }
    csrf_token_value = get_token(request)
    app_data = {
        "csrf": csrf_token_value,
        "user": (
            {"id": user.pk, "name": user.full_name, "role": user.role}
            if user
            else None
        ),
        "dashTitle": titles.get(role, "Dashboard"),
        "menu": {item["key"]: item["label"] for item in menu},
    }
    icons = {
        "dash": '<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>',
        "mapview": '<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 21s-7-6.2-7-11a7 7 0 0114 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/></svg>',
        "request": '<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 8v8M8 12h8"/></svg>',
        "volunteer": '<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.6 3-6 6.5-6s6.5 2.4 6.5 6"/></svg>',
        "manage": '<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/></svg>',
        "logout": '<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" aria-hidden="true"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/></svg>',
    }
    for item in menu:
        item["icon"] = mark_safe(icons[item["icon"]])
    response = render(
        request,
        "index.html",
        {
            "user": user,
            "role": role,
            "menu": menu,
            "dash_title": titles.get(role, "Dashboard"),
            "app_data": app_data,
            "icons": icons,
            "show_request": role in (User.Role.ADMIN, User.Role.REQUESTER),
            "show_location_sharing": role == User.Role.VOLUNTEER
            and Volunteer.objects.filter(user=user).exists(),
            "is_admin": role == User.Role.ADMIN,
            "logout_icon": mark_safe(icons["logout"]),
            "avatar_initial": user.full_name[:1].upper() if user else "",
        },
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Frame-Options"] = "SAMEORIGIN"
    response["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response["Cache-Control"] = "no-store"
    return response


@require_http_methods(["POST"])
def login_api(request):
    data = parse_body(request)
    if data is None:
        return response_error("Invalid request.")
    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")
    if not username or not password:
        return response_error("Please complete all required fields.")
    user = authenticate(request, username=username, password=password)
    if user is None:
        inactive = User.objects.filter(username=username, is_active=False).exists()
        if inactive:
            return response_error(
                "This account has been disabled. Please contact the administrator.", 403
            )
        return response_error("Invalid login credentials.", 401)
    login(request, user)
    log_activity("LOGIN", f"{user.full_name} logged in", user)
    return response_ok("Login successful.", role=user.role)


@require_http_methods(["POST"])
def register_api(request):
    data = parse_body(request)
    if data is None:
        return response_error("Invalid request.")
    username = str(data.get("username") or "").strip()
    full_name = normalized(data.get("full_name"))
    email = str(data.get("email") or "").strip()
    password = str(data.get("password") or "")
    confirm = str(data.get("confirm") or "")
    if not username or not full_name or not password:
        return response_error("Please complete all required fields.")
    if not USERNAME_PATTERN.fullmatch(username):
        return response_error(
            "Username must be 4 to 30 characters (letters, numbers, dot or underscore)."
        )
    if not 2 <= len(full_name) <= 100:
        return response_error("Full name must be 2 to 100 characters.")
    if len(email) > 120:
        return response_error("Please enter a valid email address.")
    if email:
        try:
            from django.core.validators import validate_email

            validate_email(email)
        except ValidationError:
            return response_error("Please enter a valid email address.")
    if len(password) < 8:
        return response_error("Password must be at least 8 characters.")
    if password != confirm:
        return response_error("Passwords do not match.")
    try:
        validate_password(password)
    except ValidationError:
        return response_error("Please choose a stronger password.")
    try:
        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                password=password,
                full_name=full_name,
                email=email,
                role=User.Role.REQUESTER,
            )
    except IntegrityError:
        return response_error("That username is already taken.", 409)
    log_activity("REGISTER", f"New requester account created: {username}", user)
    return response_ok("Account created successfully. You can now log in.")


@require_http_methods(["POST"])
def logout_api(request):
    user = request.user if request.user.is_authenticated else None
    if user:
        log_activity("LOGOUT", f"{user.full_name} logged out", user)
    logout(request)
    return response_ok("You have been logged out.")


@require_http_methods(["GET"])
def requests_api(request):
    user = actor_or_error(request)
    if isinstance(user, JsonResponse):
        return user
    queryset = AssistanceRequest.objects.all()
    if user.role == User.Role.REQUESTER:
        queryset = queryset.filter(user=user)
    elif user.role == User.Role.VOLUNTEER:
        queryset = queryset.filter(
            assignments__volunteer__user=user,
            assignments__status__in=(
                Assignment.Status.ACTIVE,
                Assignment.Status.COMPLETED,
            ),
        )
    status = str(request.GET.get("status") or "").strip().upper()
    if status and status != "ALL":
        if status not in REQUEST_STATUSES:
            return response_error("Invalid status filter.")
        queryset = queryset.filter(status=status)
    map_only = "map" in request.GET
    if map_only:
        queryset = queryset.filter(
            status__in=[
                AssistanceRequest.Status.PENDING,
                AssistanceRequest.Status.APPROVED,
                AssistanceRequest.Status.ASSIGNED,
                AssistanceRequest.Status.ONGOING,
            ]
        )
    query = str(request.GET.get("q") or "").strip()
    if query:
        queryset = queryset.filter(
            Q(request_code__icontains=query)
            | Q(requester_name__icontains=query)
            | Q(assistance_type__icontains=query)
            | Q(location__icontains=query)
        )
    try:
        limit = min(500, max(1, int(request.GET.get("limit", "200"))))
    except (TypeError, ValueError):
        limit = 200
    items = list(queryset.distinct().order_by("-created_at", "-id")[:limit])
    assignments = (
        Assignment.objects.exclude(status=Assignment.Status.CANCELLED)
        .filter(request_id__in=[item.pk for item in items])
        .select_related("volunteer")
        .order_by("request_id", "-id")
    )
    active_assignments = {}
    for assignment in assignments:
        active_assignments.setdefault(assignment.request_id, assignment)
    if map_only:
        data = [
            {
                key: value
                for key, value in serialize_request(
                    item, active_assignments.get(item.pk)
                ).items()
                if key in (
                    "id",
                    "request_code",
                    "assistance_type",
                    "status",
                    "urgency",
                    "location",
                    "latitude",
                    "longitude",
                )
            }
            for item in items
        ]
    else:
        data = [
            serialize_request(item, active_assignments.get(item.pk)) for item in items
        ]
    return JsonResponse({"success": True, "requests": data})


@require_http_methods(["POST"])
def create_request_api(request):
    user = actor_or_error(request, User.Role.ADMIN, User.Role.REQUESTER)
    if isinstance(user, JsonResponse):
        return user
    data = parse_body(request)
    if data is None:
        return response_error("Invalid request.")
    name = normalized(data.get("requester_name"))
    contact = str(data.get("contact") or "").strip()
    assistance_type = str(data.get("assistance_type") or "").strip()
    location = normalized(data.get("location"))
    description = str(data.get("description") or "").strip()
    urgency = str(data.get("urgency") or "").strip()
    needed_raw = str(data.get("needed_at") or "").strip()
    if not all((name, contact, assistance_type, location, description, urgency, needed_raw)):
        return response_error("Please complete all required fields.")
    if not 2 <= len(name) <= 100:
        return response_error("Requester name must be 2 to 100 characters.")
    if not CONTACT_PATTERN.fullmatch(contact):
        return response_error("Please enter a valid contact number.")
    if assistance_type not in ASSISTANCE_TYPES:
        return response_error("Please choose a valid assistance type.")
    if not 3 <= len(location) <= 255:
        return response_error("Location must be 3 to 255 characters.")
    if not 5 <= len(description) <= 2000:
        return response_error("Description must be 5 to 2000 characters.")
    if urgency not in URGENCY_LEVELS:
        return response_error("Please choose a valid urgency level.")
    needed_at = None
    for date_format in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            needed_at = datetime.strptime(needed_raw, date_format)
            break
        except ValueError:
            continue
    if needed_at is None:
        return response_error("Please enter a valid date and time.")
    needed_at = timezone.make_aware(needed_at, timezone.get_current_timezone())
    latitude, longitude, error = parse_coordinates(data)
    if error:
        return response_error(error)
    with transaction.atomic():
        item = AssistanceRequest.objects.create(
            user=user,
            requester_name=name,
            contact=contact,
            assistance_type=assistance_type,
            location=location,
            latitude=latitude,
            longitude=longitude,
            description=description,
            urgency=urgency,
            needed_at=needed_at,
        )
        item.request_code = f"REQ-{item.pk:06d}"
        item.save(update_fields=["request_code"])
    log_activity(
        "REQUEST_CREATED",
        f"{user.role.title()} submitted {item.request_code}",
        user,
        item,
    )
    return response_ok(
        "Request submitted successfully.", id=item.pk, request_code=item.request_code
    )


@require_http_methods(["POST"])
def update_request_api(request):
    user = actor_or_error(request)
    if isinstance(user, JsonResponse):
        return user
    data = parse_body(request)
    if data is None:
        return response_error("Invalid request.")
    try:
        request_id = int(data.get("id", 0))
    except (TypeError, ValueError):
        request_id = 0
    action = str(data.get("action") or "")
    if request_id <= 0 or action not in {
        "approve",
        "reject",
        "assign",
        "start",
        "complete",
        "cancel",
    }:
        return response_error("Invalid request.")

    with transaction.atomic():
        try:
            item = AssistanceRequest.objects.select_for_update().get(pk=request_id)
        except AssistanceRequest.DoesNotExist:
            return response_error("Request not found.", 404)
        assignment = (
            Assignment.objects.select_for_update()
            .filter(request=item, status=Assignment.Status.ACTIVE)
            .select_related("volunteer")
            .first()
        )
        is_admin = user.role == User.Role.ADMIN
        is_owner = item.user_id == user.pk
        is_assigned_volunteer = bool(
            assignment
            and user.role == User.Role.VOLUNTEER
            and assignment.volunteer.user_id == user.pk
        )
        status = item.status
        new_status = status
        actor_name = user.role.title()
        code = item.request_code

        if action == "approve":
            if not is_admin:
                return response_error("You do not have permission to do this.", 403)
            if status != AssistanceRequest.Status.PENDING:
                return response_error("Only pending requests can be approved.")
            new_status = AssistanceRequest.Status.APPROVED
            log = ("REQUEST_APPROVED", f"{actor_name} approved {code}")
            message = "Request successfully approved."
        elif action == "reject":
            if not is_admin:
                return response_error("You do not have permission to do this.", 403)
            if status not in (
                AssistanceRequest.Status.PENDING,
                AssistanceRequest.Status.APPROVED,
            ):
                return response_error("Only pending or approved requests can be rejected.")
            new_status = AssistanceRequest.Status.REJECTED
            log = ("REQUEST_REJECTED", f"{actor_name} rejected {code}")
            message = "Request rejected."
        elif action == "assign":
            if not is_admin:
                return response_error("You do not have permission to do this.", 403)
            if status != AssistanceRequest.Status.APPROVED:
                return response_error("Only approved requests can be assigned to a volunteer.")
            if assignment:
                return response_error("This request already has a volunteer.")
            try:
                volunteer_id = int(data.get("volunteer_id", 0))
                volunteer = Volunteer.objects.select_for_update().get(pk=volunteer_id)
            except (TypeError, ValueError, Volunteer.DoesNotExist):
                return response_error("Volunteer not found.", 404)
            if volunteer.status != Volunteer.Status.AVAILABLE:
                return response_error(
                    "This volunteer is not available. Please choose another volunteer.",
                    409,
                )
            assignment = Assignment.objects.create(
                request=item,
                volunteer=volunteer,
                assigned_by=user,
                status=Assignment.Status.ACTIVE,
            )
            volunteer.status = Volunteer.Status.BUSY
            volunteer.save(update_fields=["status"])
            new_status = AssistanceRequest.Status.ASSIGNED
            log = (
                "REQUEST_ASSIGNED",
                f"{actor_name} assigned Volunteer {volunteer.volunteer_code} to {code}",
            )
            message = "Volunteer successfully assigned."
        elif action == "start":
            if not assignment:
                return response_error("This request has no assigned volunteer.")
            if not is_admin and not is_assigned_volunteer:
                return response_error("You do not have permission to do this.", 403)
            if status != AssistanceRequest.Status.ASSIGNED:
                return response_error("Only assigned requests can be started.")
            assignment.started_at = timezone.now()
            assignment.save(update_fields=["started_at"])
            new_status = AssistanceRequest.Status.ONGOING
            log = ("REQUEST_STARTED", f"{actor_name} started {code}")
            message = "Assistance started."
        elif action == "complete":
            if not assignment:
                return response_error("This request has no assigned volunteer.")
            if not is_admin and not is_assigned_volunteer:
                return response_error("You do not have permission to do this.", 403)
            allowed = (
                (AssistanceRequest.Status.ASSIGNED, AssistanceRequest.Status.ONGOING)
                if is_admin
                else (AssistanceRequest.Status.ONGOING,)
            )
            if status not in allowed:
                return response_error("Start the assistance before completing it.")
            now = timezone.now()
            assignment.status = Assignment.Status.COMPLETED
            assignment.completed_at = now
            if not assignment.started_at:
                assignment.started_at = now
            assignment.save(
                update_fields=["status", "completed_at", "started_at"]
            )
            volunteer = assignment.volunteer
            volunteer.status = Volunteer.Status.AVAILABLE
            volunteer.save(update_fields=["status"])
            new_status = AssistanceRequest.Status.DONE
            log = ("REQUEST_COMPLETED", f"Request {code} completed")
            message = "Request successfully completed."
        else:
            if is_admin:
                allowed = (
                    AssistanceRequest.Status.PENDING,
                    AssistanceRequest.Status.APPROVED,
                    AssistanceRequest.Status.ASSIGNED,
                    AssistanceRequest.Status.ONGOING,
                )
            elif user.role == User.Role.REQUESTER and is_owner:
                allowed = (
                    AssistanceRequest.Status.PENDING,
                    AssistanceRequest.Status.APPROVED,
                )
            else:
                return response_error("You do not have permission to do this.", 403)
            if status not in allowed:
                return response_error("This request can no longer be cancelled.")
            if assignment:
                assignment.status = Assignment.Status.CANCELLED
                assignment.save(update_fields=["status"])
                volunteer = assignment.volunteer
                volunteer.status = Volunteer.Status.AVAILABLE
                volunteer.save(update_fields=["status"])
            new_status = AssistanceRequest.Status.CANCELLED
            log = ("REQUEST_CANCELLED", f"{actor_name} cancelled {code}")
            message = "Request cancelled."

        item.status = new_status
        item.save(update_fields=["status", "updated_at"])
    log_activity(log[0], log[1], user, item)
    return response_ok(message, status=new_status)


@require_http_methods(["POST"])
def delete_request_api(request):
    user = actor_or_error(request, User.Role.ADMIN)
    if isinstance(user, JsonResponse):
        return user
    data = parse_body(request)
    if data is None:
        return response_error("Invalid request.")
    try:
        request_id = int(data.get("id", 0))
    except (TypeError, ValueError):
        request_id = 0
    if request_id <= 0:
        return response_error("Invalid request.")
    with transaction.atomic():
        try:
            item = AssistanceRequest.objects.select_for_update().get(pk=request_id)
        except AssistanceRequest.DoesNotExist:
            return response_error("Request not found.", 404)
        code = item.request_code
        for assignment in Assignment.objects.filter(
            request=item, status=Assignment.Status.ACTIVE
        ).select_related("volunteer"):
            assignment.volunteer.status = Volunteer.Status.AVAILABLE
            assignment.volunteer.save(update_fields=["status"])
        item.delete()
    log_activity("REQUEST_DELETED", f"Admin deleted {code}", user)
    return response_ok("Request deleted.")


@require_http_methods(["GET"])
def volunteers_api(request):
    user = actor_or_error(request, User.Role.ADMIN)
    if isinstance(user, JsonResponse):
        return user
    queryset = Volunteer.objects.select_related("user").all()
    status = str(request.GET.get("status") or "").strip().upper()
    if status and status != "ALL":
        if status not in VOLUNTEER_STATUSES:
            return response_error("Invalid volunteer status.")
        queryset = queryset.filter(status=status)
    map_only = "map" in request.GET
    if map_only:
        queryset = queryset.filter(latitude__isnull=False, longitude__isnull=False)
    query = str(request.GET.get("q") or "").strip()
    if query:
        queryset = queryset.filter(
            Q(volunteer_code__icontains=query)
            | Q(full_name__icontains=query)
            | Q(skill__icontains=query)
            | Q(contact__icontains=query)
        )
    items = list(queryset.order_by("id"))
    active_assignments = {
        assignment.volunteer_id: assignment.request.request_code
        for assignment in Assignment.objects.filter(
            volunteer_id__in=[item.pk for item in items],
            status=Assignment.Status.ACTIVE,
        ).select_related("request")
    }
    return JsonResponse(
        {
            "success": True,
            "volunteers": [
                serialize_volunteer(item, active_assignments.get(item.pk))
                for item in items
            ],
        }
    )


@require_http_methods(["POST"])
def update_volunteer_location_api(request):
    user = actor_or_error(request, User.Role.VOLUNTEER)
    if isinstance(user, JsonResponse):
        return user
    data = parse_body(request)
    if data is None:
        return response_error("Invalid location update.")
    try:
        volunteer = Volunteer.objects.get(user=user)
    except Volunteer.DoesNotExist:
        return response_error(
            "Your account is not linked to a volunteer profile. Contact an administrator.",
            404,
        )
    if data.get("action") == "clear":
        volunteer.latitude = None
        volunteer.longitude = None
        volunteer.location_accuracy = None
        volunteer.location_updated_at = None
        volunteer.save(
            update_fields=(
                "latitude",
                "longitude",
                "location_accuracy",
                "location_updated_at",
            )
        )
        return response_ok("Your last shared location was cleared.")
    latitude, longitude, error = parse_coordinates(data)
    if error or latitude is None or longitude is None:
        return response_error(error or "Please provide your current location.")
    try:
        accuracy = Decimal(str(data.get("accuracy")))
    except (InvalidOperation, TypeError, ValueError):
        return response_error("Invalid location accuracy.")
    if not accuracy.is_finite() or accuracy < 0 or accuracy > 100000:
        return response_error("Invalid location accuracy.")
    volunteer.latitude = latitude
    volunteer.longitude = longitude
    volunteer.location_accuracy = accuracy.quantize(Decimal("0.1"))
    volunteer.location_updated_at = timezone.now()
    volunteer.save(
        update_fields=(
            "latitude",
            "longitude",
            "location_accuracy",
            "location_updated_at",
        )
    )
    return response_ok("Your live location was updated.")


@require_http_methods(["POST"])
def create_volunteer_api(request):
    user = actor_or_error(request, User.Role.ADMIN)
    if isinstance(user, JsonResponse):
        return user
    data = parse_body(request)
    if data is None:
        return response_error("Invalid request.")
    values, error = validate_volunteer_data(data)
    if error:
        return response_error(error)
    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")
    create_account = bool(username or password)
    if create_account:
        if not USERNAME_PATTERN.fullmatch(username):
            return response_error(
                "Username must be 4 to 30 characters (letters, numbers, dot or underscore)."
            )
        if len(password) < 8:
            return response_error("Password must be at least 8 characters.")
        try:
            validate_password(password)
        except ValidationError:
            return response_error("Please choose a stronger password.")
    try:
        with transaction.atomic():
            volunteer_user = None
            if create_account:
                volunteer_user = User.objects.create_user(
                    username=username,
                    password=password,
                    full_name=values["name"],
                    role=User.Role.VOLUNTEER,
                )
            volunteer = Volunteer.objects.create(
                user=volunteer_user,
                full_name=values["name"],
                contact=values["contact"],
                skill=values["skill"],
                availability=values["availability"],
                status=values["status"],
                latitude=values["latitude"],
                longitude=values["longitude"],
            )
            volunteer.volunteer_code = f"V-{volunteer.pk:04d}"
            volunteer.save(update_fields=["volunteer_code"])
    except IntegrityError:
        return response_error("That username is already taken.", 409)
    log_activity(
        "VOLUNTEER_ADDED",
        f"Admin added Volunteer {volunteer.volunteer_code} ({values['name']})",
        user,
    )
    return response_ok(
        "Volunteer added successfully.",
        id=volunteer.pk,
        volunteer_code=volunteer.volunteer_code,
    )


@require_http_methods(["POST"])
def update_volunteer_api(request):
    user = actor_or_error(request, User.Role.ADMIN)
    if isinstance(user, JsonResponse):
        return user
    data = parse_body(request)
    if data is None:
        return response_error("Invalid request.")
    try:
        volunteer_id = int(data.get("id", 0))
    except (TypeError, ValueError):
        volunteer_id = 0
    try:
        volunteer = Volunteer.objects.select_related("user").get(pk=volunteer_id)
    except Volunteer.DoesNotExist:
        return response_error("Volunteer not found.", 404)
    has_active_assignment = Assignment.objects.filter(
        volunteer=volunteer, status=Assignment.Status.ACTIVE
    ).exists()
    action = str(data.get("action") or "update")
    if action == "status":
        status = str(data.get("status") or "").strip().upper()
        if status not in VOLUNTEER_STATUSES:
            return response_error("Invalid volunteer status.")
        if has_active_assignment and status != Volunteer.Status.BUSY:
            return response_error(
                "This volunteer has an active assignment. Complete or cancel it first.",
                409,
            )
        volunteer.status = status
        volunteer.save(update_fields=["status"])
        log_activity(
            "VOLUNTEER_STATUS",
            f"Admin set Volunteer {volunteer.volunteer_code} to {status}",
            user,
        )
        return response_ok("Volunteer status updated.")
    values, error = validate_volunteer_data(data)
    if error:
        return response_error(error)
    if has_active_assignment and values["status"] != Volunteer.Status.BUSY:
        return response_error(
            "This volunteer has an active assignment. Complete or cancel it first.",
            409,
        )
    for field, key in (
        ("full_name", "name"),
        ("contact", "contact"),
        ("skill", "skill"),
        ("availability", "availability"),
        ("status", "status"),
        ("latitude", "latitude"),
        ("longitude", "longitude"),
    ):
        setattr(volunteer, field, values[key])
    with transaction.atomic():
        volunteer.save()
        if volunteer.user_id:
            User.objects.filter(pk=volunteer.user_id).update(full_name=values["name"])
    log_activity(
        "VOLUNTEER_UPDATED",
        f"Admin updated Volunteer {volunteer.volunteer_code}",
        user,
    )
    return response_ok("Volunteer updated successfully.")


@require_http_methods(["POST"])
def delete_volunteer_api(request):
    user = actor_or_error(request, User.Role.ADMIN)
    if isinstance(user, JsonResponse):
        return user
    data = parse_body(request)
    if data is None:
        return response_error("Invalid request.")
    try:
        volunteer_id = int(data.get("id", 0))
        volunteer = Volunteer.objects.select_related("user").get(pk=volunteer_id)
    except (TypeError, ValueError, Volunteer.DoesNotExist):
        return response_error("Volunteer not found.", 404)
    if Assignment.objects.filter(
        volunteer=volunteer, status=Assignment.Status.ACTIVE
    ).exists():
        return response_error(
            "This volunteer has an active assignment and cannot be deleted.", 409
        )
    code = volunteer.volunteer_code
    name = volunteer.full_name
    volunteer_user_id = volunteer.user_id
    with transaction.atomic():
        volunteer.delete()
        if volunteer_user_id:
            User.objects.filter(
                pk=volunteer_user_id, role=User.Role.VOLUNTEER
            ).delete()
    log_activity(
        "VOLUNTEER_DELETED",
        f"Admin deleted Volunteer {code} ({name})",
        user,
    )
    return response_ok("Volunteer deleted.")


@require_http_methods(["GET", "POST"])
def dashboard_api(request):
    user = actor_or_error(request)
    if isinstance(user, JsonResponse):
        return user
    if request.method == "GET":
        action = str(request.GET.get("action") or "")
    else:
        data = parse_body(request)
        if data is None:
            return response_error("Invalid request.")
        action = str(data.get("action") or "")
    if action in ("users", "logs", "toggle_user") and user.role != User.Role.ADMIN:
        return response_error("You do not have permission to do this.", 403)

    if action == "stats" and request.method == "GET":
        requests = AssistanceRequest.objects.all()
        if user.role == User.Role.REQUESTER:
            requests = requests.filter(user=user)
        elif user.role == User.Role.VOLUNTEER:
            requests = requests.filter(
                assignments__volunteer__user=user,
                assignments__status__in=(
                    Assignment.Status.ACTIVE,
                    Assignment.Status.COMPLETED,
                ),
            ).distinct()
        stats = {
            "total": requests.count(),
            "pending": requests.filter(status=AssistanceRequest.Status.PENDING).count(),
            "approved": requests.filter(status=AssistanceRequest.Status.APPROVED).count(),
            "assigned": requests.filter(status=AssistanceRequest.Status.ASSIGNED).count(),
            "ongoing": requests.filter(status=AssistanceRequest.Status.ONGOING).count(),
            "done": requests.filter(status=AssistanceRequest.Status.DONE).count(),
        }
        volunteers = {
            "total": Volunteer.objects.count(),
            "available": Volunteer.objects.filter(
                status=Volunteer.Status.AVAILABLE
            ).count(),
        }
        activities = ActivityLog.objects.exclude(
            action__in=("LOGIN", "LOGOUT", "REGISTER")
        )
        if user.role == User.Role.REQUESTER:
            activities = activities.filter(Q(user=user) | Q(request__user=user))
        elif user.role == User.Role.VOLUNTEER:
            activities = activities.filter(
                Q(user=user)
                | Q(request__assignments__volunteer__user=user)
            )
        activities = [
            {
                "id": item.pk,
                "action": item.action,
                "details": item.details,
                "created_at": item.created_at.isoformat(),
                "full_name": item.user.full_name if item.user_id else None,
            }
            for item in activities.select_related("user").distinct()[:8]
        ]
        return JsonResponse(
            {
                "success": True,
                "stats": stats,
                "volunteers": volunteers,
                "activities": activities,
            }
        )
    if action == "users" and request.method == "GET":
        rows = User.objects.order_by("id").values(
            "id", "username", "full_name", "email", "role", "is_active", "created_at"
        )
        return JsonResponse(
            {
                "success": True,
                "users": [
                    {**row, "created_at": row["created_at"].isoformat()}
                    for row in rows
                ],
            }
        )
    if action == "logs" and request.method == "GET":
        rows = ActivityLog.objects.select_related("user").order_by("-id")[:300]
        return JsonResponse(
            {
                "success": True,
                "logs": [
                    {
                        "id": row.pk,
                        "action": row.action,
                        "details": row.details,
                        "created_at": row.created_at.isoformat(),
                        "full_name": row.user.full_name if row.user_id else None,
                    }
                    for row in rows
                ],
            }
        )
    if action == "toggle_user" and request.method == "POST":
        try:
            target_id = int(data.get("id", 0))
        except (TypeError, ValueError):
            target_id = 0
        if target_id == user.pk:
            return response_error("You cannot disable your own account.", 409)
        try:
            target = User.objects.get(pk=target_id)
        except User.DoesNotExist:
            return response_error("User not found.", 404)
        target.is_active = not target.is_active
        target.save(update_fields=["is_active"])
        action_name = "USER_ENABLED" if target.is_active else "USER_DISABLED"
        log_activity(
            action_name,
            f"Admin {'enabled' if target.is_active else 'disabled'} account {target.username}",
            user,
        )
        return response_ok(
            "Account enabled." if target.is_active else "Account disabled."
        )
    return response_error("Invalid request.")
