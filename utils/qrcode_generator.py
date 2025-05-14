#!/usr/bin/env python3
import os
import sys

import qrcode


def generate_qrcode(text, filename="qrcode.png"):
    """
    Generate a QR code from the given text and save it to a file.

    Args:
        text: The string to encode in the QR code
        filename: The file name to save the QR code image (default: qrcode.png)

    Returns:
        Path to the saved QR code image
    """
    # Create QR code instance
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )

    # Add data to the QR code
    qr.add_data(text)
    qr.make(fit=True)

    # Create an image from the QR code
    img = qr.make_image(fill_color="black", back_color="white")

    # Save the image
    img.save(filename)
    return os.path.abspath(filename)


if __name__ == "__main__":
    # Get input from command line arguments or prompt user
    if len(sys.argv) > 1:
        text = sys.argv[1]
        filename = sys.argv[2] if len(sys.argv) > 2 else "qrcode.png"
    else:
        text = input("Enter the text for the QR code: ")
        filename = input("Enter filename to save QR code (default: qrcode.png): ") or "qrcode.png"

    # Generate the QR code
    output_path = generate_qrcode(text, filename)
    print(f"QR code generated and saved to: {output_path}")
