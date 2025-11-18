from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    abort,
    flash,
)
from sqlalchemy import desc

from src.database import get_db
from src.models import (
    Sale,
    ReturnItem,
    ReturnRequest,
    ReturnRequestStatus,
    ReturnReason,
    InspectionResult,
    RefundMethod,
)
from src.services.returns_service import ReturnsService

returns_bp = Blueprint("returns", __name__)


def _ensure_authenticated() -> Optional[Any]:
    if "user_id" not in session:
        return redirect(url_for("login"))
    return None


def _is_admin() -> bool:
    # Lightweight admin gate – user ID 1 or explicitly flagged in the session.
    return session.get("is_admin") or session.get("user_id") == 1


def _require_admin() -> None:
    if not _is_admin():
        abort(403)


def _get_returns_service() -> ReturnsService:
    return ReturnsService(get_db())


@returns_bp.context_processor
def inject_return_enums():
    return {
        "ReturnRequestStatus": ReturnRequestStatus,
        "ReturnReason": ReturnReason,
        "InspectionResult": InspectionResult,
        "RefundMethod": RefundMethod,
    }


@returns_bp.route("/returns", methods=["GET"])
def view_returns():
    redirect_response = _ensure_authenticated()
    if redirect_response:
        return redirect_response

    db = get_db()
    user_id = session["user_id"]

    completed_sales = (
        db.query(Sale)
        .filter_by(userID=user_id)
        .filter(Sale._status == "completed")
        .order_by(desc(Sale._sale_date))
        .limit(10)
        .all()
    )
    return_requests = (
        db.query(ReturnRequest)
        .filter_by(customerID=user_id)
        .order_by(desc(ReturnRequest.created_at))
        .all()
    )

    return render_template(
        "returns.html",
        sales=completed_sales,
        return_requests=return_requests,
        is_admin=_is_admin(),
    )


@returns_bp.route("/returns/request", methods=["POST"])
def submit_return_request():
    redirect_response = _ensure_authenticated()
    if redirect_response:
        return redirect_response

    sale_id = request.form.get("sale_id")
    reason = request.form.get("reason")
    details = request.form.get("details")
    photos = request.form.get("photos_url")

    if not sale_id or not reason:
        flash("Sale and reason are required to submit a return.", "error")
        return redirect(url_for("returns.view_returns"))

    try:
        sale_id_int = int(sale_id)
    except ValueError:
        flash("Invalid sale identifier supplied.", "error")
        return redirect(url_for("returns.view_returns"))

    items_payload = _extract_item_quantities(request.form)

    if not items_payload:
        flash("Please select at least one item to return.", "error")
        return redirect(url_for("returns.view_returns"))

    success, message, _ = _get_returns_service().create_return_request(
        sale_id=sale_id_int,
        customer_id=session["user_id"],
        items=items_payload,
        reason=reason,
        details=details,
        photos_url=photos,
    )
    flash(message, "success" if success else "error")
    return redirect(url_for("returns.view_returns"))


@returns_bp.route("/api/returns", methods=["GET"])
def api_list_returns():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    db = get_db()
    requests = (
        db.query(ReturnRequest)
        .filter_by(customerID=session["user_id"])
        .order_by(desc(ReturnRequest.created_at))
        .all()
    )
    return jsonify({"returns": [_serialize_return_request(r) for r in requests]})


@returns_bp.route("/api/returns", methods=["POST"])
def api_create_return():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    payload = request.get_json(silent=True) or {}
    sale_id = payload.get("sale_id")
    reason = payload.get("reason")
    items = payload.get("items", [])

    if not sale_id or not reason or not isinstance(items, list):
        return jsonify({"error": "sale_id, reason, and items are required"}), 400

    success, message, request_obj = _get_returns_service().create_return_request(
        sale_id=sale_id,
        customer_id=session["user_id"],
        items=items,
        reason=reason,
        details=payload.get("details"),
        photos_url=payload.get("photos_url"),
    )

    status_code = 200 if success else 400
    response: Dict[str, Any] = {"success": success, "message": message}
    if request_obj:
        response["return"] = _serialize_return_request(request_obj)
    return jsonify(response), status_code


@returns_bp.route("/admin/returns", methods=["GET"])
def admin_returns_dashboard():
    redirect_response = _ensure_authenticated()
    if redirect_response:
        return redirect_response
    _require_admin()

    db = get_db()
    return_requests = (
        db.query(ReturnRequest)
        .order_by(desc(ReturnRequest.created_at))
        .all()
    )
    return render_template(
        "admin_returns.html",
        return_requests=return_requests,
        is_admin=True,
    )


@returns_bp.route("/admin/returns/<int:return_id>/authorize", methods=["POST"])
def admin_authorize_return(return_id: int):
    redirect_response = _ensure_authenticated()
    if redirect_response:
        return redirect_response
    _require_admin()

    approve = request.form.get("decision", "approve") == "approve"
    notes = request.form.get("decision_notes")
    return _handle_admin_action(
        lambda: _get_returns_service().authorize_return(return_id, approve, notes)
    )


@returns_bp.route("/admin/returns/<int:return_id>/shipment", methods=["POST"])
def admin_record_shipment(return_id: int):
    redirect_response = _ensure_authenticated()
    if redirect_response:
        return redirect_response
    _require_admin()

    carrier = request.form.get("carrier")
    tracking = request.form.get("tracking_number")

    if not carrier or not tracking:
        flash("Carrier and tracking number are required.", "error")
        return redirect(url_for("returns.admin_returns_dashboard"))

    return _handle_admin_action(
        lambda: _get_returns_service().record_shipment(return_id, carrier, tracking)
    )


@returns_bp.route("/admin/returns/<int:return_id>/receive", methods=["POST"])
def admin_mark_received(return_id: int):
    redirect_response = _ensure_authenticated()
    if redirect_response:
        return redirect_response
    _require_admin()

    return _handle_admin_action(
        lambda: _get_returns_service().mark_received(return_id)
    )


@returns_bp.route("/admin/returns/<int:return_id>/inspection", methods=["POST"])
def admin_record_inspection(return_id: int):
    redirect_response = _ensure_authenticated()
    if redirect_response:
        return redirect_response
    _require_admin()

    result = request.form.get("result")
    inspected_by = request.form.get("inspected_by", "QA Bot")
    notes = request.form.get("notes")

    if not result:
        flash("Inspection result is required.", "error")
        return redirect(url_for("returns.admin_returns_dashboard"))

    return _handle_admin_action(
        lambda: _get_returns_service().record_inspection(
            return_id,
            inspected_by,
            result,
            notes,
        )
    )


@returns_bp.route("/admin/returns/<int:return_id>/refund", methods=["POST"])
def admin_initiate_refund(return_id: int):
    redirect_response = _ensure_authenticated()
    if redirect_response:
        return redirect_response
    _require_admin()

    method = request.form.get("method")
    success, message = _get_returns_service().initiate_refund(return_id, method=method)
    flash(message, "success" if success else "error")
    return redirect(url_for("returns.admin_returns_dashboard"))


# ---------------------------
# Admin JSON APIs
# ---------------------------


@returns_bp.route("/api/admin/returns", methods=["GET"])
def api_admin_returns():
    if "user_id" not in session or not _is_admin():
        return jsonify({"error": "Forbidden"}), 403

    db = get_db()
    return_requests = (
        db.query(ReturnRequest)
        .order_by(desc(ReturnRequest.created_at))
        .all()
    )
    return jsonify({"returns": [_serialize_return_request(r) for r in return_requests]})


@returns_bp.route("/api/admin/returns/<int:return_id>/authorize", methods=["POST"])
def api_admin_authorize(return_id: int):
    if "user_id" not in session or not _is_admin():
        return jsonify({"error": "Forbidden"}), 403

    payload = request.get_json(silent=True) or {}
    approve = payload.get("approve", True)
    notes = payload.get("decision_notes")
    success, message, request_obj = _get_returns_service().authorize_return(
        return_id,
        bool(approve),
        notes,
    )
    return _json_admin_response(success, message, request_obj)


@returns_bp.route("/api/admin/returns/<int:return_id>/shipment", methods=["POST"])
def api_admin_shipment(return_id: int):
    if "user_id" not in session or not _is_admin():
        return jsonify({"error": "Forbidden"}), 403

    payload = request.get_json(silent=True) or {}
    carrier = payload.get("carrier")
    tracking = payload.get("tracking_number")
    success, message, request_obj = _get_returns_service().record_shipment(
        return_id, carrier, tracking
    )
    return _json_admin_response(success, message, request_obj)


@returns_bp.route("/api/admin/returns/<int:return_id>/receive", methods=["POST"])
def api_admin_receive(return_id: int):
    if "user_id" not in session or not _is_admin():
        return jsonify({"error": "Forbidden"}), 403

    success, message, request_obj = _get_returns_service().mark_received(return_id)
    return _json_admin_response(success, message, request_obj)


@returns_bp.route("/api/admin/returns/<int:return_id>/inspection", methods=["POST"])
def api_admin_inspection(return_id: int):
    if "user_id" not in session or not _is_admin():
        return jsonify({"error": "Forbidden"}), 403

    payload = request.get_json(silent=True) or {}
    result = payload.get("result")
    inspected_by = payload.get("inspected_by", "QA Bot")
    notes = payload.get("notes")

    success, message, request_obj = _get_returns_service().record_inspection(
        return_id, inspected_by, result, notes
    )
    return _json_admin_response(success, message, request_obj)


@returns_bp.route("/api/admin/returns/<int:return_id>/refund", methods=["POST"])
def api_admin_refund(return_id: int):
    if "user_id" not in session or not _is_admin():
        return jsonify({"error": "Forbidden"}), 403

    payload = request.get_json(silent=True) or {}
    method = payload.get("method")
    success, message = _get_returns_service().initiate_refund(
        return_id,
        method=method,
    )
    status = 200 if success else 400
    return jsonify({"success": success, "message": message}), status


# ---------------------------
# Helpers
# ---------------------------


def _extract_item_quantities(form_data: Dict[str, Any]) -> List[Dict[str, int]]:
    items: List[Dict[str, int]] = []
    for key, value in form_data.items():
        if not key.startswith("quantity_"):
            continue
        try:
            sale_item_id = int(key.split("_")[1])
            quantity = int(value or 0)
        except (ValueError, IndexError):
            continue
        if quantity > 0:
            items.append({"sale_item_id": sale_item_id, "quantity": quantity})
    return items


def _serialize_return_request(return_request: ReturnRequest) -> Dict[str, Any]:
    shipment = return_request.shipment
    inspection = return_request.inspection
    refund = return_request.refund

    return {
        "id": return_request.returnRequestID,
        "sale_id": return_request.saleID,
        "customer_id": return_request.customerID,
        "status": _enum_value(return_request.status),
        "reason": return_request.reason.value if isinstance(return_request.reason, ReturnReason) else return_request.reason,
        "details": return_request.details,
        "created_at": _serialize_dt(return_request.created_at),
        "updated_at": _serialize_dt(return_request.updated_at),
        "items": [_serialize_return_item(item) for item in return_request.return_items],
        "shipment": {
            "carrier": shipment.carrier,
            "tracking_number": shipment.tracking_number,
            "shipped_at": _serialize_dt(shipment.shipped_at),
            "received_at": _serialize_dt(shipment.received_at),
            "notes": shipment.notes,
        } if shipment else None,
        "inspection": {
            "result": _enum_value(inspection.result),
            "inspected_by": inspection.inspected_by,
            "inspected_at": _serialize_dt(inspection.inspected_at),
            "notes": inspection.notes,
        } if inspection else None,
        "refund": {
            "id": refund.refundID,
            "amount": float(refund.amount) if refund.amount is not None else None,
            "method": _enum_value(refund.method),
            "status": _enum_value(refund.status),
            "failure_reason": refund.failure_reason,
            "processed_at": _serialize_dt(refund.processed_at),
        } if refund else None,
    }


def _serialize_return_item(item: ReturnItem) -> Dict[str, Any]:
    product = item.sale_item.product if item.sale_item else None
    return {
        "sale_item_id": item.saleItemID,
        "product_id": product.productID if product else None,
        "product_name": product.name if product else None,
        "quantity": item.quantity,
        "requested_refund_amount": item.requested_refund_amount,
    }


def _serialize_dt(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _handle_admin_action(
    action_func,
) -> Any:
    success, message, _ = action_func()
    flash(message, "success" if success else "error")
    return redirect(url_for("returns.admin_returns_dashboard"))


def _json_admin_response(success: bool, message: str, request_obj: Optional[ReturnRequest]):
    status = 200 if success else 400
    body: Dict[str, Any] = {"success": success, "message": message}
    if request_obj:
        body["return"] = _serialize_return_request(request_obj)
    return jsonify(body), status

