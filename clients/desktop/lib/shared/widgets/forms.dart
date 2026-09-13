import 'package:flutter/material.dart'
    show Material, Colors, TextField, InputDecoration, OutlineInputBorder, Slider, Switch;
import 'package:flutter/widgets.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/theme/magnus_theme.dart';

/// Controles de formulario temados, compartidos por las páginas. Envuelven los
/// de Material en un [Material] transparente para vivir dentro de Fluent/macOS.

class MagnusTextField extends StatelessWidget {
  const MagnusTextField({
    super.key,
    required this.controller,
    required this.hint,
    this.onSubmitted,
    this.maxLines = 1,
    this.minLines = 1,
    this.mono = false,
  });

  final TextEditingController controller;
  final String hint;
  final ValueChanged<String>? onSubmitted;
  final int maxLines;
  final int minLines;
  final bool mono;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    OutlineInputBorder border(Color c) => OutlineInputBorder(
          borderRadius: BorderRadius.circular(t.radius),
          borderSide: BorderSide(color: c),
        );
    return Material(
      color: Colors.transparent,
      child: TextField(
        controller: controller,
        minLines: minLines,
        maxLines: maxLines,
        style: mono ? t.mono : TextStyle(color: t.text, fontSize: 13.5),
        onSubmitted: onSubmitted,
        decoration: InputDecoration(
          isDense: true,
          filled: true,
          fillColor: t.surfaceAlt,
          hintText: hint,
          hintStyle: TextStyle(color: t.textFaint),
          border: border(t.stroke),
          enabledBorder: border(t.stroke),
          focusedBorder: border(t.accent),
        ),
      ),
    );
  }
}

/// Opción seleccionable en forma de chip.
class ChoiceChipX extends StatelessWidget {
  const ChoiceChipX({
    super.key,
    required this.label,
    required this.selected,
    required this.onTap,
    this.icon,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
          decoration: BoxDecoration(
            color: selected ? t.accent : t.surfaceAlt,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: selected ? t.accent : t.stroke),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (icon != null) ...[
                Icon(icon, size: 13, color: selected ? t.onAccent : t.textMuted),
                const SizedBox(width: 5),
              ],
              Text(label,
                  style: TextStyle(
                      fontSize: 12.5,
                      fontWeight: FontWeight.w600,
                      color: selected ? t.onAccent : t.textMuted)),
            ],
          ),
        ),
      ),
    );
  }
}

class SliderField extends StatelessWidget {
  const SliderField({
    super.key,
    required this.label,
    required this.value,
    required this.min,
    required this.max,
    required this.unit,
    required this.onChanged,
    this.divisions,
  });

  final String label;
  final double value;
  final double min;
  final double max;
  final String unit;
  final int? divisions;
  final ValueChanged<double> onChanged;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return Material(
      color: Colors.transparent,
      child: Row(
        children: [
          SizedBox(width: 150, child: Text(label, style: t.body)),
          Expanded(
            child: Slider(
              value: value.clamp(min, max),
              min: min,
              max: max,
              divisions: divisions,
              activeColor: t.accent,
              inactiveColor: t.surfaceAlt,
              onChanged: onChanged,
            ),
          ),
          SizedBox(
            width: 90,
            child: Text('${value.toStringAsFixed(0)} $unit',
                textAlign: TextAlign.right, style: t.small.copyWith(color: t.text)),
          ),
        ],
      ),
    );
  }
}

class ToggleField extends StatelessWidget {
  const ToggleField({
    super.key,
    required this.label,
    required this.value,
    required this.onChanged,
    this.hint,
  });

  final String label;
  final String? hint;
  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return Material(
      color: Colors.transparent,
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: t.body.copyWith(fontWeight: FontWeight.w600)),
                if (hint != null) Text(hint!, style: t.small),
              ],
            ),
          ),
          Switch(
            value: value,
            activeThumbColor: t.onAccent,
            activeTrackColor: t.accent,
            inactiveThumbColor: t.textMuted,
            inactiveTrackColor: t.surfaceAlt,
            onChanged: onChanged,
          ),
        ],
      ),
    );
  }
}

/// Aviso en línea: error (rojo), advertencia (ámbar) o información.
class InlineNotice extends StatelessWidget {
  const InlineNotice(this.message, {super.key, this.kind = NoticeKind.error, this.onClose});

  final String message;
  final NoticeKind kind;
  final VoidCallback? onClose;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final (color, icon) = switch (kind) {
      NoticeKind.error => (t.bad, LucideIcons.circleAlert),
      NoticeKind.warning => (t.warn, LucideIcons.circleAlert),
      NoticeKind.info => (t.info, LucideIcons.info),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(t.radius),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Icon(icon, color: color, size: 16),
          ),
          const SizedBox(width: 10),
          Expanded(child: Text(message, style: t.body.copyWith(color: t.text))),
          if (onClose != null)
            GestureDetector(
              onTap: onClose,
              child: Icon(LucideIcons.x, size: 14, color: t.textFaint),
            ),
        ],
      ),
    );
  }
}

enum NoticeKind { error, warning, info }

/// Etiqueta de campo con texto de ayuda opcional.
class FieldLabel extends StatelessWidget {
  const FieldLabel(this.text, {super.key, this.hint});
  final String text;
  final String? hint;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(text, style: t.body.copyWith(fontWeight: FontWeight.w600)),
          if (hint != null) Text(hint!, style: t.small),
        ],
      ),
    );
  }
}
