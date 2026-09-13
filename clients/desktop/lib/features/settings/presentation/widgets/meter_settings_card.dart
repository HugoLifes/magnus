import 'package:flutter/widgets.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../../core/di/injector.dart';
import '../../../../core/error/failures.dart';
import '../../../../core/network/api_models.dart';
import '../../../../core/network/magnus_api.dart';
import '../../../../core/theme/magnus_theme.dart';
import '../../../../shared/widgets/forms.dart';
import '../../../../shared/widgets/ui.dart';

const _cloudReferences = [
  'auto',
  'gpt-4o-mini',
  'gemini-2.5-flash',
  'gpt-5-mini',
  'claude-haiku-4.5',
  'gpt-5',
  'gemini-2.5-pro',
  'claude-sonnet-4.5',
];

/// Ajustes del medidor que viven en el daemon: con estos datos calcula el coste
/// local de cada respuesta y el ahorro frente a la nube.
class MeterSettingsCard extends StatefulWidget {
  const MeterSettingsCard({super.key});
  @override
  State<MeterSettingsCard> createState() => _MeterSettingsCardState();
}

class _MeterSettingsCardState extends State<MeterSettingsCard> {
  final _api = sl<MagnusApi>();
  final _electricity = TextEditingController();
  final _hardware = TextEditingController();
  final _years = TextEditingController();
  final _hours = TextEditingController();
  String _reference = 'auto';
  String? _error;
  String? _saved;
  bool _loaded = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    for (final c in [_electricity, _hardware, _years, _hours]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final s = await _api.daemonSettings();
      if (!mounted) return;
      setState(() => _apply(s));
    } on Failure catch (f) {
      if (mounted) setState(() => _error = f.message);
    }
  }

  void _apply(DaemonSettings s) {
    _electricity.text = s.electricityUsdPerKwh.toString();
    _hardware.text = s.hardwareCostUsd?.toStringAsFixed(0) ?? '';
    _years.text = s.hardwareLifetimeYears.toString();
    _hours.text = s.hoursPerDay.toString();
    _reference = _cloudReferences.contains(s.cloudReference) ? s.cloudReference : 'auto';
    _loaded = true;
    _error = null;
  }

  Future<void> _save() async {
    double? parse(TextEditingController c) => double.tryParse(c.text.trim().replaceAll(',', '.'));
    final electricity = parse(_electricity);
    final years = parse(_years);
    final hours = parse(_hours);
    if (electricity == null || years == null || hours == null) {
      setState(() => _error = 'Revisa los números: tarifa, años y horas son obligatorios.');
      return;
    }
    try {
      final s = await _api.updateDaemonSettings({
        'electricity_usd_per_kwh': electricity,
        // Vacío: el daemon usa el precio de referencia de tu familia de hardware.
        'hardware_cost_usd': _hardware.text.trim().isEmpty ? null : parse(_hardware),
        'hardware_lifetime_years': years,
        'hours_per_day': hours,
        'cloud_reference': _reference,
      });
      if (!mounted) return;
      setState(() {
        _apply(s);
        _saved = 'Guardado: vale desde la siguiente respuesta.';
      });
    } on Failure catch (f) {
      if (mounted) setState(() => _error = f.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(LucideIcons.coins, size: 16, color: t.ok),
              const SizedBox(width: 8),
              Text('Medidor de coste', style: t.h2),
            ],
          ),
          const SizedBox(height: 4),
          Text('Con esto se calcula cuánto cuesta cada respuesta en tu equipo y cuánto '
              'te ahorras frente a la nube. Cifras en USD.', style: t.small),
          const SizedBox(height: 14),
          if (_error != null) ...[
            InlineNotice(_error!, onClose: () => setState(() => _error = null)),
            const SizedBox(height: 10),
          ],
          if (_saved != null) ...[
            InlineNotice(_saved!, kind: NoticeKind.info, onClose: () => setState(() => _saved = null)),
            const SizedBox(height: 10),
          ],
          if (!_loaded && _error == null)
            Text('Leyendo ajustes del daemon…', style: t.small)
          else ...[
            Wrap(
              spacing: 16,
              runSpacing: 12,
              children: [
                _NumberField(label: 'Electricidad (USD/kWh)', controller: _electricity, hint: '0.15'),
                _NumberField(label: 'Precio del equipo (USD)', controller: _hardware, hint: 'referencia'),
                _NumberField(label: 'Vida útil (años)', controller: _years, hint: '3'),
                _NumberField(label: 'Horas de uso al día', controller: _hours, hint: '4'),
              ],
            ),
            const SizedBox(height: 14),
            const FieldLabel('Comparar contra',
                hint: 'auto elige el modelo de nube de tamaño parecido al local, el más barato de su clase.'),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final r in _cloudReferences)
                  ChoiceChipX(label: r, selected: r == _reference, onTap: () => setState(() => _reference = r)),
              ],
            ),
            const SizedBox(height: 14),
            MagnusButton(label: 'Guardar', icon: LucideIcons.check, onTap: _save),
          ],
        ],
      ),
    );
  }
}

class _NumberField extends StatelessWidget {
  const _NumberField({required this.label, required this.controller, required this.hint});
  final String label;
  final TextEditingController controller;
  final String hint;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 200,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          FieldLabel(label),
          MagnusTextField(controller: controller, hint: hint),
        ],
      ),
    );
  }
}
