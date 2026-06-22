/// Constantes globales del cliente de escritorio.
class AppConstants {
  AppConstants._();

  /// URL por defecto del daemon de Magnus (API local). Configurable en Ajustes.
  static const String defaultDaemonUrl = 'http://127.0.0.1:8420';

  /// Cuantizaciones que se evalúan al construir la matriz (de mayor a menor calidad).
  /// Debe coincidir con QUANT_PREFERENCE del núcleo Python (core/compatibility.py).
  static const List<String> quants = ['fp16', 'fp8', 'q8', 'q6', 'q5', 'q4'];

  /// Presets de hardware de destino (coinciden con core/hardware.py HARDWARE_PRESETS).
  static const List<String> targets = [
    'auto',
    'b200',
    'gb200',
    'h200',
    'h100',
    'a100-80',
    'dgx-spark',
    'rtx-5090',
    'rtx-4090',
  ];

  /// Claves de preferencias persistidas.
  static const String prefDesignSystem = 'design_system';
  static const String prefDaemonUrl = 'daemon_url';
  static const String prefAppearance = 'appearance';
  static const String prefFont = 'font_family';
  static const String prefUseSystemAccent = 'use_system_accent';

  /// Fuente por defecto (misma en los 3 diseños) y opciones ofrecidas en Ajustes.
  static const String defaultFont = 'Plus Jakarta Sans';
  static const List<String> fonts = [
    'Plus Jakarta Sans',
    'Inter',
    'Manrope',
    'Outfit',
    'DM Sans',
    'Space Grotesk',
  ];

  /// Tamaño mínimo de ventana — clave para que el entorno se ajuste bien.
  static const double minWindowWidth = 720;
  static const double minWindowHeight = 540;
}
