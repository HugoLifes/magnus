import 'dart:io' show Platform;

import 'package:flutter/widgets.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../../core/theme/magnus_theme.dart';
import '../../../../shared/widgets/ui.dart';
import '../../../models/presentation/bloc/models_bloc.dart';

/// Sección Recursos/Salud: estado del servidor de inferencia (donde el uso
/// constante de la IA desgasta el hardware) y de este equipo (caché local).
/// GPU es real (vía `/hardware`); CPU/RAM/disco esperan el endpoint `/system`.
class ResourcesPage extends StatelessWidget {
  const ResourcesPage({super.key});

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return BlocBuilder<ModelsBloc, ModelsState>(
      builder: (context, state) {
        final gpus = state.gpus;
        return PageScaffold(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SectionHeader(
                icon: LucideIcons.heartPulse,
                title: 'Recursos y salud',
                subtitle: 'Vigila el desgaste por uso continuo de la IA.',
              ),

              // --- Servidor (host del daemon) ---
              Row(
                children: [
                  Icon(LucideIcons.server, size: 16, color: t.accent),
                  const SizedBox(width: 8),
                  Text('Servidor de inferencia', style: t.h2),
                ],
              ),
              const SizedBox(height: 4),
              Text('La máquina que monta y ejecuta los modelos.', style: t.small),
              const SizedBox(height: 12),

              if (gpus.isEmpty)
                GlassCard(
                  child: Text(
                      'Sin datos de GPU. ¿Está corriendo el daemon con acceso a la GPU?',
                      style: t.body),
                )
              else
                Wrap(
                  spacing: 14,
                  runSpacing: 14,
                  children: [
                    for (final g in gpus)
                      _MetricCard(
                        icon: LucideIcons.cpu,
                        title: 'GPU ${g.index} · VRAM',
                        sub: g.name,
                        used: g.totalGib - g.freeGib,
                        total: g.totalGib,
                        unit: 'GiB',
                      ),
                  ],
                ),
              const SizedBox(height: 14),
              const Wrap(
                spacing: 14,
                runSpacing: 14,
                children: [
                  _PendingMetric(icon: LucideIcons.cpu, title: 'CPU del servidor'),
                  _PendingMetric(icon: LucideIcons.memoryStick, title: 'RAM del servidor'),
                  _PendingMetric(icon: LucideIcons.hardDrive, title: 'Disco / modelos'),
                ],
              ),
              const SizedBox(height: 26),

              // --- Este equipo ---
              Row(
                children: [
                  Icon(LucideIcons.laptop, size: 16, color: t.info),
                  const SizedBox(width: 8),
                  Text('Este equipo', style: t.h2),
                ],
              ),
              const SizedBox(height: 12),
              GlassCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Especificaciones detectadas', style: t.h2),
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 22,
                      runSpacing: 14,
                      children: [
                        _Spec(LucideIcons.monitor, 'Sistema', _osName()),
                        _Spec(LucideIcons.cpu, 'CPU lógicas',
                            '${Platform.numberOfProcessors} hilos'),
                        _Spec(LucideIcons.server, 'Equipo', _host()),
                        _Spec(LucideIcons.code, 'Runtime',
                            'Dart ${Platform.version.split(' ').first}'),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              GlassCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          width: 36,
                          height: 36,
                          decoration: BoxDecoration(
                            color: t.info.withValues(alpha: 0.16),
                            borderRadius: BorderRadius.circular(t.radius),
                          ),
                          alignment: Alignment.center,
                          child: Icon(LucideIcons.sparkles,
                              size: 18, color: t.info),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('Caché del cliente', style: t.h2),
                              const SizedBox(height: 2),
                              Text(
                                  'Miniaturas, respuestas y archivos temporales de la app.',
                                  style: t.small),
                            ],
                          ),
                        ),
                        MagnusButton(
                          label: 'Limpiar caché',
                          icon: LucideIcons.trash2,
                          primary: false,
                          onTap: () {}, // limpieza local del cliente
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              // --- Consejos de salud ---
              GlassCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(LucideIcons.heart, size: 16, color: t.bad),
                        const SizedBox(width: 8),
                        Text('Salud del hardware', style: t.h2),
                      ],
                    ),
                    const SizedBox(height: 12),
                    _Tip(t, 'Mantén la VRAM por debajo del 90% para evitar throttling térmico.'),
                    _Tip(t, 'Descarga (unload) modelos inactivos para liberar memoria.'),
                    _Tip(t, 'Vigila la temperatura de la GPU en cargas sostenidas.'),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({
    required this.icon,
    required this.title,
    required this.sub,
    required this.used,
    required this.total,
    required this.unit,
  });
  final IconData icon;
  final String title;
  final String sub;
  final double used;
  final double total;
  final String unit;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final frac = total > 0 ? (used / total).clamp(0.0, 1.0) : 0.0;
    final pct = frac * 100;
    final color = pct > 85 ? t.bad : (pct > 60 ? t.warn : t.ok);
    return SizedBox(
      width: 330,
      child: GlassCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, size: 16, color: t.accent),
                const SizedBox(width: 8),
                Expanded(
                    child: Text(title,
                        style: t.body.copyWith(fontWeight: FontWeight.w600))),
                Pill('${pct.toStringAsFixed(0)}%', color: color),
              ],
            ),
            const SizedBox(height: 4),
            Text(sub, style: t.small, maxLines: 1, overflow: TextOverflow.ellipsis),
            const SizedBox(height: 14),
            UsageBar(fraction: frac.toDouble(), color: color),
            const SizedBox(height: 8),
            Text('${used.toStringAsFixed(1)} / ${total.toStringAsFixed(0)} $unit',
                style: t.small),
          ],
        ),
      ),
    );
  }
}

class _PendingMetric extends StatelessWidget {
  const _PendingMetric({required this.icon, required this.title});
  final IconData icon;
  final String title;
  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return SizedBox(
      width: 330,
      child: GlassCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, size: 16, color: t.textMuted),
                const SizedBox(width: 8),
                Expanded(
                    child: Text(title,
                        style: t.body.copyWith(fontWeight: FontWeight.w600))),
                Pill('pendiente', color: t.textFaint),
              ],
            ),
            const SizedBox(height: 14),
            UsageBar(fraction: 0, color: t.textMuted),
            const SizedBox(height: 8),
            Text('Espera el endpoint /system del daemon', style: t.small),
          ],
        ),
      ),
    );
  }
}

class _Tip extends StatelessWidget {
  const _Tip(this.t, this.text);
  final MagnusTheme t;
  final String text;
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 5),
            child: Icon(LucideIcons.circleCheck, size: 14, color: t.ok),
          ),
          const SizedBox(width: 10),
          Expanded(child: Text(text, style: t.body)),
        ],
      ),
    );
  }
}

/// Una especificación detectada (icono + etiqueta + valor).
class _Spec extends StatelessWidget {
  const _Spec(this.icon, this.label, this.value);
  final IconData icon;
  final String label;
  final String value;
  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 18, color: t.textMuted),
        const SizedBox(width: 10),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(label, style: t.small.copyWith(color: t.textFaint)),
            Text(value, style: t.body.copyWith(fontWeight: FontWeight.w600)),
          ],
        ),
      ],
    );
  }
}

String _osName() {
  const pretty = {
    'windows': 'Windows',
    'macos': 'macOS',
    'linux': 'Linux',
    'android': 'Android',
    'ios': 'iOS',
  };
  return pretty[Platform.operatingSystem] ?? Platform.operatingSystem;
}

String _host() {
  try {
    return Platform.localHostname;
  } catch (_) {
    return '—';
  }
}
