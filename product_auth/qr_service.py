"""QR code generation for product authenticity verification.

Each product gets a unique serial (UUID4, not sequential/guessable - a
counterfeiter shouldn't be able to enumerate valid serials by incrementing
a number). The QR encodes a verification payload (tenant + serial) that the
scanning client sends to POST /scan.

SVG output (not PNG) deliberately - it needs no Pillow/native imaging
dependency, which keeps this installable in restricted/offline
environments, consistent with the TF-IDF-over-embeddings choice in rag/.
"""
import io
import uuid

import qrcode
import qrcode.image.svg


def generate_serial() -> str:
    return f"PRD-{uuid.uuid4().hex[:12].upper()}"


def generate_qr_svg(serial: str, tenant_id: str) -> str:
    """Returns the QR code as an SVG string. The encoded payload is a
    verification URL-shaped string carrying both the serial and tenant, so
    a scan can be validated without a separate lookup step to find which
    tenant a serial belongs to."""
    payload = f"verify://{tenant_id}/{serial}"
    factory = qrcode.image.svg.SvgImage
    img = qrcode.make(payload, image_factory=factory, box_size=8, border=2)
    buffer = io.BytesIO()
    img.save(buffer)
    return buffer.getvalue().decode("utf-8")
