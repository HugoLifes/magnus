import 'package:flutter/widgets.dart';

import '../../../../core/di/injector.dart';
import '../../../../core/error/failures.dart';
import '../../../../core/network/api_models.dart';
import '../../../../core/network/magnus_api.dart';
import '../../../../core/theme/icons.dart';
import '../../../../core/theme/magnus_theme.dart';
import '../../../../shared/widgets/skeleton.dart';
import '../../../../shared/widgets/ui.dart';

/// Qué puede hacer Magnus Code en este equipo, sin prometer de más.
///
/// Es la tarjeta que evita la decepción: en una laptop de 4 GiB dice que lee y
/// propone, y a dónde ir para lo demás; en una de 16 dice qué modelo bajar y
/// cuánto pesa. El dato sale del daemon (`/code/capability`), que lo calcula con
/// la memoria real y el catálogo.
class CodeCapabilityCard extends StatefulWidget {
  const CodeCapabilityCard({super.key});

  @override
  State<CodeCapabilityCard> createState() => _CodeCapabilityCardState();
}

class _CodeCapabilityCardState extends State<CodeCapabilityCard> {
  final _api = sl<MagnusApi>();
  CodeCapabilityInfo? _cap;
  String? _error;
  double? _progreso; // descarga en curso: 0..1

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final cap = await _api.codeCapability();
      if (mounted) setState(() => _cap = cap);
    } on Failure catch (f) {
      if (mounted) setState(() => _error = f.message);
    }
  }

  /// Descarga el modelo recomendado sin salir de aquí.
  ///
  /// En una app, decirle a alguien que escriba `magnus fetch …` en una terminal
  /// es perder a la mitad de la gente por el camino.
  Future<void> _descargar(String id) async {
    setState(() {
      _progreso = 0;
      _error = null;
    });
    try {
      await for (final p in _api.pullModel(id)) {
        if (!mounted) return;
        setState(() => _progreso = (p.percent ?? 0) / 100);
      }
      if (!mounted) return;
      setState(() => _progreso = null);
      await _load();
    } on Failure catch (f) {
      if (mounted) {
        setState(() {
          _progreso = null;
          _error = f.message;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final cap = _cap;
    return GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(context.icons.build, size: 15, color: t.accent),
              const SizedBox(width: 8),
              Text('MAGNUS CODE', style: t.eyebrow),
              const Spacer(),
              if (cap != null)
                Pill(
                  cap.tierLabel,
                  color: cap.canAutonomous ? t.ok : t.textMuted,
                  icon: cap.canAutonomous ? context.icons.success : context.icons.info,
                ),
            ],
          ),
          const SizedBox(height: 10),
          if (_error != null)
            Text(_error!, style: t.small.copyWith(color: t.bad))
          else if (cap == null)
            Skeleton.lines(2, width: 420)
          else ...[
            Text(cap.headline, style: t.body),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final modo in cap.modes)
                  Pill(_modoLabel(modo), color: t.accent, icon: context.icons.check),
                if (cap.modelName != null)
                  Pill(
                    cap.modelDownloaded
                        ? '${cap.modelName} · descargado'
                        : '${cap.modelName} · ${cap.downloadGib!.toStringAsFixed(1)} GiB',
                    color: cap.modelDownloaded ? t.ok : t.info,
                    icon: cap.modelDownloaded ? context.icons.success : context.icons.download,
                  ),
              ],
            ),
            if (cap.modelId != null && !cap.modelDownloaded) ...[
              const SizedBox(height: 14),
              if (_progreso != null) ...[
                UsageBar(fraction: _progreso!),
                const SizedBox(height: 6),
                Text('Descargando ${cap.modelName}… ${(_progreso! * 100).toStringAsFixed(0)} %',
                    style: t.small),
              ] else
                MagnusButton(
                  label: 'Descargar ${cap.modelName} · ${cap.downloadGib!.toStringAsFixed(1)} GiB',
                  icon: context.icons.download,
                  onTap: () => _descargar(cap.modelId!),
                ),
            ],
            if (cap.advice.isNotEmpty) ...[
              const SizedBox(height: 12),
              for (final consejo in cap.advice.where(
                  (c) => !(c.startsWith('Descárgalo con') && cap.modelId != null)))
                Padding(
                  padding: const EdgeInsets.only(bottom: 5),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(context.icons.tip, size: 13, color: t.textFaint),
                      const SizedBox(width: 8),
                      Expanded(child: Text(consejo, style: t.small)),
                    ],
                  ),
                ),
            ],
          ],
        ],
      ),
    );
  }

  static String _modoLabel(String modo) => switch (modo) {
        'plan' => 'Plan',
        'preguntar' => 'Preguntar',
        'aceptar_ediciones' => 'Aceptar ediciones',
        'autonomo' => 'Autónomo',
        _ => modo,
      };
}
