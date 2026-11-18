{
  pkgs,
  lib,
  ...
}: {
  dotenv.enable = false;

  env = {
    UV_PYTHON = "3.15";
    UV_PYTHON_PREFERENCE = "only-system";
    UV_PYTHON_DOWNLOADS = "never";
    PYTHONNOUSERSITE = "1";
    LD_LIBRARY_PATH = lib.makeLibraryPath [pkgs.stdenv.cc.cc.lib pkgs.zlib];
  };
  enterShell =
    (import (builtins.fetchurl {
        url = "https://raw.githubusercontent.com/NostraDavid/nixcfg/cb2423e55f4a7ee010d33a649ddf0488338baa42/nix/system-tools.nix";
        sha256 = "7d2abe646d9389e296c5e1cafa0b63dd52e9821c58037d9dd8faef90124104e2";
      })
      pkgs [
        "python315"
        {
          attr = "uv";
          series = "0";
          also = ["uvx"];
        }
        "just"
        "git"
      ])
    + ''
      unset PYTHONPATH PYTHONHOME _PYTHON_SYSCONFIGDATA_NAME
    '';
}
