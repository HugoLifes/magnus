import 'dart:io' show Platform;

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../../core/di/injector.dart';
import '../../../../core/network/api_models.dart';
import '../../../../core/theme/magnus_theme.dart';
import '../../../../shared/format.dart';
import '../../../../shared/widgets/forms.dart';
import '../../../../shared/widgets/ui.dart';
import '../cubit/system_cubit.dart';

/// Recursos: telemetría en vivo del host del daemon (uso de GPU, potencia,
/// temperatura, memoria) y el perfil de la familia NVIDIA detectada.
class ResourcesPage extends StatelessWidget {
  const ResourcesPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => sl<SystemCubit>()..start(),
      child: const _ResourcesView(),
    );
  }
}

class _ResourcesView extends StatelessWidget {
  const _ResourcesView();

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return BlocBuilder<SystemCubit, SystemState>(
      builder: (context, state) {
        final sample = state.sample;
        final platform = state.platform;
        return PageScaffold(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SectionHeader(
                icon: LucideIcons.heartPulse,
                title: 'Recursos y salud',
                subtitle: 'Telemetría en vivo del equipo que ejecuta los modelos.',
                trailing: state.health == null
                    ? null
                    : Pill(
                        state.health!.ollama
                            ? 'Ollama ${state.health!.ollamaVersion ?? ''}'
                            : 'Ollama no responde',
                        color: state.health!.ollama ? t.ok : t.bad,
                        icon: LucideIcons.plug,
                      ),
              ),
              if (state.error != null) ...[
                InlineNotice(state.error!),
                const SizedBox(height: 14),
              ],
              if (platform != null) _PlatformCard(platform),
              const SizedBox(height: 14),
              if (sample == null)
                GlassCard(child: Text('Leyendo sensores…', style: t.small))
              else ...[
                Wrap(
                  spacing: 14,
                  runSpacing: 14,
                  children: [
                    for (final g in sample.gpus) _GpuCard(g),
                    _PowerCard(sample: sample, history: state.history),
                    if (sample.ramTotalGib != null)
                      _BarCard(
                        icon: LucideIcons.memoryStick,
                        title: 'Memoria del sistema',
                        sub: platform?.unifiedMemory == true
                            ? 'Compartida con la GPU'
                            : 'RAM',
                        used: sample.ramTotalGib! - (sample.ramAvailableGib ?? 0),
                        total: sample.ramTotalGib!,
                      ),
                  ],
                ),
                if (sample.gpus.isEmpty) ...[
                  const SizedBox(height: 12),
                  GlassCard(
                    child: Text('No se detectó GPU NVIDIA en el host del daemon.', style: t.body),
                  ),
                ],
              ],
              const SizedBox(height: 22),
              Row(
                children: [
                  Icon(LucideIcons.laptop, size: 16, color: t.info),
                  const SizedBox(width: 8),
                  Text('Este equipo (cliente)', style: t.h2),
                ],
              ),
              const SizedBox(height: 12),
              GlassCard(
                child: Wrap(
                  spacing: 22,
                  runSpacing: 14,
                  children: [
                    _Spec(LucideIcons.monitor, 'Sistema', _osName()),
                    _Spec(LucideIcons.cpu, 'CPU lógicas', '${Platform.numberOfProcessors} hilos'),
                    _Spec(LucideIcons.server, 'Equipo', _host()),
                  ],
                ),
              ),
              const SizedBox(height: 16),
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
                    const _Tip('Mantén la memoria de la GPU por debajo del 90 % para evitar throttling.'),
                    const _Tip('Libera los modelos que no uses: en memoria compartida es lo que más ayuda.'),
                    const _Tip('Por encima de 85 °C sostenidos conviene mejorar la ventilación.'),
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

class _PlatformCard extends StatelessWidget {
  const _PlatformCard(this.p);
  final PlatformInfo p;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(LucideIcons.server, size: 16, color: t.accent),
              const SizedBox(width: 8),
              Expanded(child: Text(p.displayName.isEmpty ? 'Servidor' : p.displayName, style: t.h2)),
              Pill(p.familyLabel, color: t.accent),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 26,
            runSpacing: 12,
            children: [
              _Spec(LucideIcons.database, 'Memoria',
                  '${p.totalMemoryGib.toStringAsFixed(1)} GiB${p.unifiedMemory ? ' unificada' : ''}'),
              _Spec(LucideIcons.layers, 'Modelos a la vez', '${p.maxLoadedModels}'),
              _Spec(LucideIcons.sparkles, 'Tamaño sugerido', 'hasta ~${p.suggestedMaxParamsB} B (q4)'),
              _Spec(LucideIcons.wrench, 'Runtimes', p.runtimes.join(', ')),
            ],
          ),
          for (final note in p.notes) ...[
            const SizedBox(height: 8),
            _Tip(note),
          ],
        ],
      ),
    );
  }
}

class _GpuCard extends StatelessWidget {
  const _GpuCard(this.g);
  final GpuSample g;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final util = (g.utilizationPct ?? 0) / 100;
    final memFrac = (g.memoryTotalGib ?? 0) > 0 ? (g.memoryUsedGib ?? 0) / g.memoryTotalGib! : 0.0;
    final temp = g.temperatureC;
    return SizedBox(
      width: 330,
      child: GlassCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(LucideIcons.cpu, size: 16, color: t.accent),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(g.name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: t.body.copyWith(fontWeight: FontWeight.w600)),
                ),
                if (temp != null)
                  Pill('${temp.toStringAsFixed(0)} °C',
                      color: temp > 85 ? t.bad : (temp > 70 ? t.warn : t.ok),
                      icon: LucideIcons.thermometer),
              ],
            ),
            const SizedBox(height: 14),
            _LabeledBar('Uso de GPU', formatNum(g.utilizationPct, decimals: 0, unit: ' %'), util, t.accent),
            const SizedBox(height: 10),
            _LabeledBar(
              g.unifiedMemory ? 'Memoria (compartida)' : 'VRAM',
              '${formatNum(g.memoryUsedGib)} / ${formatGib(g.memoryTotalGib)}',
              memFrac,
              memFrac > 0.85 ? t.bad : (memFrac > 0.6 ? t.warn : t.ok),
            ),
            if (g.powerW != null) ...[
              const SizedBox(height: 10),
              Text('${g.powerW!.toStringAsFixed(1)} W', style: t.small),
            ],
          ],
        ),
      ),
    );
  }
}

class _PowerCard extends StatelessWidget {
  const _PowerCard({required this.sample, required this.history});
  final SystemSample sample;
  final List<double> history;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final maxY = history.isEmpty ? 10.0 : (history.reduce((a, b) => a > b ? a : b) * 1.25);
    return SizedBox(
      width: 330,
      child: GlassCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(LucideIcons.plug, size: 16, color: t.warn),
                const SizedBox(width: 8),
                Expanded(
                    child: Text(sample.boardPowerW != null ? 'Consumo de la placa' : 'Consumo de GPU',
                        style: t.body.copyWith(fontWeight: FontWeight.w600))),
                Text(formatNum(sample.powerW, unit: ' W'), style: t.h2),
              ],
            ),
            const SizedBox(height: 4),
            Text('Es lo que usa el medidor para el coste de energía.', style: t.small),
            const SizedBox(height: 12),
            SizedBox(
              height: 70,
              child: history.length < 2
                  ? Center(child: Text('Midiendo…', style: t.small))
                  : LineChart(
                      LineChartData(
                        minY: 0,
                        maxY: maxY,
                        titlesData: const FlTitlesData(show: false),
                        gridData: const FlGridData(show: false),
                        borderData: FlBorderData(show: false),
                        lineTouchData: const LineTouchData(enabled: false),
                        lineBarsData: [
                          LineChartBarData(
                            spots: [
                              for (var i = 0; i < history.length; i++) FlSpot(i.toDouble(), history[i]),
                            ],
                            isCurved: true,
                            color: t.warn,
                            barWidth: 2,
                            dotData: const FlDotData(show: false),
                            belowBarData: BarAreaData(show: true, color: t.warn.withValues(alpha: 0.15)),
                          ),
                        ],
                      ),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class _BarCard extends StatelessWidget {
  const _BarCard({
    required this.icon,
    required this.title,
    required this.sub,
    required this.used,
    required this.total,
  });
  final IconData icon;
  final String title;
  final String sub;
  final double used;
  final double total;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final frac = total > 0 ? (used / total).clamp(0.0, 1.0) : 0.0;
    final color = frac > 0.85 ? t.bad : (frac > 0.6 ? t.warn : t.ok);
    return SizedBox(
      width: 330,
      child: GlassCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, size: 16, color: t.info),
                const SizedBox(width: 8),
                Expanded(child: Text(title, style: t.body.copyWith(fontWeight: FontWeight.w600))),
                Pill('${(frac * 100).toStringAsFixed(0)}%', color: color),
              ],
            ),
            const SizedBox(height: 4),
            Text(sub, style: t.small),
            const SizedBox(height: 14),
            UsageBar(fraction: frac, color: color),
            const SizedBox(height: 8),
            Text('${used.toStringAsFixed(1)} / ${total.toStringAsFixed(1)} GiB', style: t.small),
          ],
        ),
      ),
    );
  }
}

class _LabeledBar extends StatelessWidget {
  const _LabeledBar(this.label, this.value, this.fraction, this.color);
  final String label;
  final String value;
  final double fraction;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(child: Text(label, style: t.small)),
            Text(value, style: t.small.copyWith(color: t.text)),
          ],
        ),
        const SizedBox(height: 5),
        UsageBar(fraction: fraction, color: color),
      ],
    );
  }
}

class _Tip extends StatelessWidget {
  const _Tip(this.text);
  final String text;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Icon(LucideIcons.circleCheck, size: 14, color: t.ok),
          ),
          const SizedBox(width: 10),
          Expanded(child: Text(text, style: t.body)),
        ],
      ),
    );
  }
}

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
  const pretty = {'windows': 'Windows', 'macos': 'macOS', 'linux': 'Linux'};
  return pretty[Platform.operatingSystem] ?? Platform.operatingSystem;
}

String _host() {
  try {
    return Platform.localHostname;
  } catch (_) {
    return '—';
  }
}
