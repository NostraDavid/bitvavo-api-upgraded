{
  pkgs,
  lib,
  ...
}: {
  dotenv.enable = false;
  packages = [pkgs.python315 pkgs.uv pkgs.just pkgs.git];
  env = {
    UV_PYTHON = "3.15";
    UV_PYTHON_PREFERENCE = "only-system";
    UV_PYTHON_DOWNLOADS = "never";
    PYTHONNOUSERSITE = "1";
    LD_LIBRARY_PATH = lib.makeLibraryPath [pkgs.stdenv.cc.cc.lib pkgs.zlib];
  };
  enterShell = ''
    unset PYTHONPATH PYTHONHOME _PYTHON_SYSCONFIGDATA_NAME
  '';
}
