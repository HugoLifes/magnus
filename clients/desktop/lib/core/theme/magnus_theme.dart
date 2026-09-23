
import 'package:flutter/widgets.dart';
import 'package:google_fonts/google_fonts.dart';

import 'brand.dart';
import 'design_system.dart';

/// Apariencia clara/oscura. Independiente del sistema de diseño.
enum Appearance {
  dark('Oscuro'),
  light('Claro');

  const Appearance(this.label);
  final String label;

  Brightness get brightness =>
      this == Appearance.dark ? Brightness.dark : Brightness.light;

  static Appearance fromName(String? name) => Appearance.values.firstWhere(
        (a) => a.name == name,
        orElse: () => Appearance.dark, // oscuro por defecto: se ve más premium
      );
}

/// Tokens visuales del contenido, **provistos por cada shell** según el diseño
/// elegido (Windows/Material/Apple) y la apariencia (claro/oscuro).
///
/// Dos capas conviven a propósito:
///
/// - **La marca** (misma en los tres temas y en la web): tinta nocturna, el
///   degradado violeta→celeste, el ámbar reservado al dinero, los títulos en
///   Bricolage Grotesque y las cifras en JetBrains Mono tabular. Es lo que hace
///   que Magnus se reconozca de lejos.
/// - **La piel nativa** (distinta por tema): superficies, profundidad, escala de
///   esquinas, densidad y el set de iconos (ver `icons.dart`). Es lo que hace
///   que no se sienta una app extraña dentro del sistema.
@immutable
class MagnusTheme {
  const MagnusTheme({
    required this.design,
    required this.brightness,
    required this.bg,
    required this.bgElevated,
    required this.surface,
    required this.surfaceStrong,
    required this.surfaceAlt,
    required this.stroke,
    required this.strokeStrong,
    required this.accent,
    required this.accentSoft,
    required this.onAccent,
    required this.ok,
    required this.warn,
    required this.bad,
    required this.info,
    required this.text,
    required this.textMuted,
    required this.textFaint,
    required this.radiusSm,
    required this.radius,
    required this.radiusLg,
    required this.glass,
    required this.blurSigma,
    required this.shadow,
    required this.uiFamily,
    required this.displayFamily,
    required this.spotlight,
    required this.density,
  });

  final DesignSystem design;
  final Brightness brightness;

  // Superficies
  final Color bg; // fondo base de la página
  final Color bgElevated; // cabeceras y barras sobre el fondo
  final Color surface; // relleno de tarjeta (translúcido si glass)
  final Color surfaceStrong; // tarjeta destacada / hover
  final Color surfaceAlt; // pistas, tracks, fondos secundarios
  final Color stroke; // bordes hairline
  final Color strokeStrong; // bordes de elementos enfocados/seleccionados

  // Marca / estados
  final Color accent;
  final Color accentSoft; // acento al 12-16% para fondos
  final Color onAccent; // texto sobre acento
  final Color ok;
  final Color warn;
  final Color bad;
  final Color info;

  // Texto
  final Color text;
  final Color textMuted;
  final Color textFaint;

  // Forma / efectos
  final double radiusSm;
  final double radius;
  final double radiusLg;
  final bool glass; // usar BackdropFilter en tarjetas
  final double blurSigma;
  final List<BoxShadow> shadow;

  /// Intensidad del foco de luz que sigue al cursor en las tarjetas (0 = nada).
  /// Es el mismo gesto de la web; en Material se baja porque ahí manda el color.
  final double spotlight;

  /// Multiplicador de espaciado: Material respira más que Fluent.
  final double density;

  /// Familias tipográficas. [displayFamily] es de marca (igual en los tres
  /// temas); [uiFamily] es la del sistema o la que el usuario eligió.
  final String uiFamily;
  final String displayFamily;

  bool get isDark => brightness == Brightness.dark;

  /// Degradado de marca para botones primarios y acentos grandes.
  LinearGradient get brandGradient => LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [accent, Color.alphaBlend(Brand.sky.withValues(alpha: 0.75), accent)],
      );

  // --- Tipografía derivada (color desde tokens) ---
  TextStyle get display => GoogleFonts.getFont(displayFamily,
      fontSize: 30,
      height: 1.05,
      fontWeight: FontWeight.w800,
      letterSpacing: -1.0,
      color: text);
  TextStyle get h1 => GoogleFonts.getFont(displayFamily,
      fontSize: 21, height: 1.15, fontWeight: FontWeight.w700, letterSpacing: -0.5, color: text);
  TextStyle get h2 => GoogleFonts.getFont(uiFamily,
      fontSize: 15, fontWeight: FontWeight.w600, letterSpacing: -0.1, color: text);
  TextStyle get body => GoogleFonts.getFont(uiFamily,
      fontSize: 13.5, height: 1.45, color: text);
  TextStyle get small => GoogleFonts.getFont(uiFamily,
      fontSize: 12, height: 1.35, fontWeight: FontWeight.w500, color: textMuted);

  /// Etiqueta corta en mayúsculas sobre un título, como en la web.
  TextStyle get eyebrow => GoogleFonts.getFont(uiFamily,
      fontSize: 10.5,
      height: 1.2,
      fontWeight: FontWeight.w700,
      letterSpacing: 1.6,
      color: accent);

  TextStyle get mono => GoogleFonts.jetBrainsMono(
      fontSize: 12.5,
      height: 1.3,
      color: text,
      fontFeatures: const [FontFeature.tabularFigures()]);

  /// Cifras grandes: monoespaciadas y tabulares, así no bailan al actualizarse.
  TextStyle get numeral => GoogleFonts.jetBrainsMono(
      fontSize: 26,
      height: 1.05,
      fontWeight: FontWeight.w600,
      letterSpacing: -0.5,
      color: text,
      fontFeatures: const [FontFeature.tabularFigures()]);

  /// Relleno de estado (hover/press) según el diseño: Material usa capas de
  /// color sobre la superficie; Fluent y Apple aclaran u oscurecen.
  Color stateLayer({bool pressed = false}) => design == DesignSystem.material
      ? accent.withValues(alpha: pressed ? 0.16 : 0.08)
      : (isDark
          ? Color(pressed ? 0x1FFFFFFF : 0x14FFFFFF)
          : Color(pressed ? 0x14000000 : 0x0A000000));

  // ----------------------------------------------------------------------
  // Fábrica: tokens por (diseño × apariencia).
  // ----------------------------------------------------------------------
  factory MagnusTheme.forDesign(
    DesignSystem design,
    Brightness b, {
    String font = 'Plus Jakarta Sans',
    Color? accent, // acento del sistema (M3 dynamic / Fluent personal)
  }) {
    final dark = b == Brightness.dark;
    final hasA = accent != null;
    final aSoft = hasA ? accent.withValues(alpha: dark ? 0.30 : 0.14) : null;
    final aOn = hasA
        ? (accent.computeLuminance() > 0.55
            ? const Color(0xFF101018)
            : const Color(0xFFFFFFFF))
        : null;
    // Títulos de marca: los mismos en los tres temas y en la web.
    const brandDisplay = 'Bricolage Grotesque';

    switch (design) {
      // ---------------- WINDOWS — Fluent: Mica, capas y acento personal -----
      case DesignSystem.windows:
        return MagnusTheme(
          design: design,
          brightness: b,
          uiFamily: font,
          displayFamily: brandDisplay,
          // Tinta nocturna de la marca (#0E0B1A) como base del modo oscuro.
          bg: dark ? Brand.night : const Color(0xFFF3F2FA),
          bgElevated: dark ? const Color(0xFF15112A) : const Color(0xFFFBFAFE),
          surface: dark ? const Color(0x14FFFFFF) : const Color(0xCCFFFFFF),
          surfaceStrong: dark ? const Color(0x1FFFFFFF) : const Color(0xFFFFFFFF),
          surfaceAlt: dark ? const Color(0x0DFFFFFF) : const Color(0x0D101030),
          stroke: dark ? const Color(0x1AECEAFB) : const Color(0x14101030),
          strokeStrong: dark ? const Color(0x38ECEAFB) : const Color(0x29101030),
          accent: accent ?? (dark ? Brand.violet : Brand.violetDeep),
          accentSoft: aSoft ?? (dark ? const Color(0x2E8B7BFF) : const Color(0x1A5A4FCF)),
          onAccent: aOn ?? const Color(0xFFFFFFFF),
          ok: Brand.teal,
          warn: Brand.amber,
          bad: Brand.rose,
          info: Brand.sky,
          text: dark ? const Color(0xFFECEAFB) : const Color(0xFF15122B),
          textMuted: dark ? const Color(0xFFB1ADCC) : const Color(0xFF55516E),
          textFaint: dark ? const Color(0xFF7F7A99) : const Color(0xFF8985A0),
          radiusSm: 6,
          radius: 10,
          radiusLg: 16,
          glass: true,
          blurSigma: 30,
          spotlight: 1,
          density: 1,
          shadow: [
            BoxShadow(
              color: Color(dark ? 0x80000000 : 0x1A0B0817),
              blurRadius: 34,
              offset: const Offset(0, 14),
            ),
          ],
        );

      // ---------------- MATERIAL — Material You: tonal, sin glass ----------
      case DesignSystem.material:
        return MagnusTheme(
          design: design,
          brightness: b,
          uiFamily: font,
          displayFamily: brandDisplay,
          bg: dark ? const Color(0xFF141218) : const Color(0xFFFEF7FF),
          bgElevated: dark ? const Color(0xFF1D1B20) : const Color(0xFFF7F2FA),
          surface: dark ? const Color(0xFF1D1B20) : const Color(0xFFFFFFFF),
          surfaceStrong: dark ? const Color(0xFF2B2930) : const Color(0xFFF7F2FA),
          surfaceAlt: dark ? const Color(0xFF211F26) : const Color(0xFFECE6F0),
          stroke: dark ? const Color(0x1FFFFFFF) : const Color(0x14000000),
          strokeStrong: dark ? const Color(0x3DFFFFFF) : const Color(0x24000000),
          accent: accent ?? (dark ? const Color(0xFFD0BCFF) : const Color(0xFF6750A4)),
          accentSoft: aSoft ?? (dark ? const Color(0x3D6750A4) : const Color(0x166750A4)),
          onAccent: aOn ?? (dark ? const Color(0xFF381E72) : const Color(0xFFFFFFFF)),
          // Turquesa, no verde: el verde es de NVIDIA (ver brand.dart).
          ok: dark ? Brand.teal : const Color(0xFF0E9384),
          warn: const Color(0xFFE0A100),
          bad: const Color(0xFFE5484D),
          info: const Color(0xFF4AA8E0),
          text: dark ? const Color(0xFFE6E0E9) : const Color(0xFF1D1B20),
          textMuted: dark ? const Color(0xFFCAC4D0) : const Color(0xFF49454F),
          textFaint: dark ? const Color(0xFF948F99) : const Color(0xFF79747E),
          // Escala de esquinas de Material 3: 12 / 16 / 28.
          radiusSm: 12,
          radius: 16,
          radiusLg: 28,
          glass: false,
          blurSigma: 0,
          spotlight: 0.35,
          density: 1.12,
          shadow: [
            BoxShadow(
              color: Color(dark ? 0x40000000 : 0x14000000),
              blurRadius: 14,
              offset: const Offset(0, 3),
            ),
          ],
        );

      // ---------------- APPLE — vibrancy sobria (macOS) -------------------
      case DesignSystem.apple:
        return MagnusTheme(
          design: design,
          brightness: b,
          uiFamily: font,
          displayFamily: brandDisplay,
          bg: dark ? const Color(0xFF1C1C1E) : const Color(0xFFECECEE),
          bgElevated: dark ? const Color(0xFF232325) : const Color(0xFFF7F7F9),
          surface: dark ? const Color(0x14FFFFFF) : const Color(0xF2FFFFFF),
          surfaceStrong: dark ? const Color(0x1FFFFFFF) : const Color(0xFFFFFFFF),
          surfaceAlt: dark ? const Color(0x0DFFFFFF) : const Color(0x0D000000),
          stroke: dark ? const Color(0x1AFFFFFF) : const Color(0x14000000),
          strokeStrong: dark ? const Color(0x33FFFFFF) : const Color(0x26000000),
          accent: accent ?? (dark ? const Color(0xFF8E7BFF) : const Color(0xFF6E56CF)),
          accentSoft: aSoft ?? (dark ? const Color(0x268E7BFF) : const Color(0x176E56CF)),
          onAccent: aOn ?? const Color(0xFFFFFFFF),
          // systemTeal de Apple en lugar de systemGreen (el verde es de NVIDIA).
          ok: dark ? const Color(0xFF40C8E0) : const Color(0xFF1F9DB3),
          warn: const Color(0xFFFFD60A),
          bad: const Color(0xFFFF6482),
          info: const Color(0xFF64D2FF),
          text: dark ? const Color(0xFFF5F5F7) : const Color(0xFF1D1D1F),
          textMuted: dark ? const Color(0xFFAEAEB2) : const Color(0xFF6E6E73),
          textFaint: const Color(0xFF8E8E93),
          radiusSm: 7,
          radius: 11,
          radiusLg: 18,
          glass: true,
          blurSigma: 22,
          spotlight: 0.5,
          density: 0.96,
          shadow: [
            BoxShadow(
              color: Color(dark ? 0x4D000000 : 0x14000000),
              blurRadius: 20,
              offset: const Offset(0, 8),
            ),
          ],
        );
    }
  }

  // ----------------------------------------------------------------------
  // InheritedWidget para exponerlo en el árbol.
  // ----------------------------------------------------------------------
  static MagnusTheme of(BuildContext context) {
    final scope =
        context.dependOnInheritedWidgetOfExactType<_MagnusThemeScope>();
    assert(scope != null, 'No MagnusTheme en el árbol. Envuelve con MagnusTheme.provide.');
    return scope!.theme;
  }

  /// Envuelve [child] proveyendo este theme a los descendientes.
  Widget provide({required Widget child}) =>
      _MagnusThemeScope(theme: this, child: child);
}

class _MagnusThemeScope extends InheritedWidget {
  const _MagnusThemeScope({required this.theme, required super.child});
  final MagnusTheme theme;

  @override
  bool updateShouldNotify(_MagnusThemeScope old) => old.theme != theme;
}
