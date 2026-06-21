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

  static DesignSystem fromName(String? name) {
    return DesignSystem.values.firstWhere(
      (d) => d.name == name,
      orElse: () => DesignSystem.windows, // por defecto, foco en escritorio Windows
    );
  }
}
