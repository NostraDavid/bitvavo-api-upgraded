{
  pkgs,
  lib,
  ...
}: {
  dotenv.enable = false;
  packages = [pkgs.python313 pkgs.uv pkgs.just pkgs.git];
  env = {
    UV_PYTHON = "3.13";
    UV_PYTHON_PREFERENCE = "only-system";
    UV_PYTHON_DOWNLOADS = "never";
    PYTHONNOUSERSITE = "1";
    LD_LIBRARY_PATH = lib.makeLibraryPath [pkgs.stdenv.cc.cc.lib pkgs.zlib];
  };
  enterShell = ''
    unset PYTHONPATH PYTHONHOME _PYTHON_SYSCONFIGDATA_NAME
  '';
}
