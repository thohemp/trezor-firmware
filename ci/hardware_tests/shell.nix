with import (builtins.fetchTarball {
  url = "https://github.com/mmilata/nixpkgs/archive/99fdcb8acd2b916b84f9bf6586df8a6b6e67a370.tar.gz";
  sha256 = "08i0y5q3da8g4pwffx8vv4rb37xvfncs1x1bh3hc3abbrxfpnc39";
}) { };

stdenv.mkDerivation rec {
  name = "trezor-firmware-hardware-tests";
  buildInputs = [
    uhubctl
    ffmpeg
    poetry
    libusb1
    dejavu_fonts
  ];
  LD_LIBRARY_PATH = "${libusb1}/lib";
  NIX_ENFORCE_PURITY = 0;
}
