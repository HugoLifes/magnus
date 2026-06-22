import 'package:flutter/foundation.dart' show TargetPlatform;

/// Los tres sistemas de diseño nativos entre los que el usuario puede elegir.
///
/// - [windows]: Fluent / WinUI (paquete fluent_ui)
/// - [material]: Material 3 de Android (incluido en el SDK de Flutter)
/// - [apple]: macOS de escritorio (paquete macos_ui; Cupertino es de iOS)
enum DesignSystem {
  windows('Windows (Fluent)'),
  material('Android (Material)'),
  apple('Apple (macOS)');

  const DesignSystem(this.label);
  final String label;

  /// Diseño por defecto según la plataforma del dispositivo (se usa sólo si el
  /// usuario no ha elegido uno). Así la app arranca en el entorno nativo.
  static DesignSystem forPlatform(TargetPlatform platform) {
    switch (platform) {
      case TargetPlatform.macOS:
      case TargetPlatform.iOS:
        return DesignSystem.apple;
      case TargetPlatform.android:
      case TargetPlatform.fuchsia:
        return DesignSystem.material;
      case TargetPlatform.windows:
        return DesignSystem.windows;
      case TargetPlatform.linux:
        return DesignSystem.material; // GTK/Material es lo más cercano nativo
    }
  }

  /// Resuelve desde la preferencia guardada; si no hay, autodetecta por
  /// plataforma con [fallback].
  static DesignSystem fromName(String? name, {DesignSystem? fallback}) {
    return DesignSystem.values.firstWhere(
      (d) => d.name == name,
      orElse: () => fallback ?? DesignSystem.windows,
    );
  }
}
