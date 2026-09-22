import 'package:flutter/widgets.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/network/api_models.dart';
import '../../../../core/theme/brand.dart';
import '../../../../core/theme/icons.dart';
import '../../../../core/theme/magnus_theme.dart';
import '../../../../shared/format.dart';
import '../../../../shared/widgets/magnus_kit.dart';
import '../../../../shared/widgets/ui.dart';
import '../../domain/entities.dart';
import '../bloc/models_bloc.dart';
import '../cubit/overview_cubit.dart';
import '../widgets/code_capability_card.dart';

/// Vista de inicio: qué puede correr este equipo, cifras clave y hardware.
class DashboardPage extends StatelessWidget {
  const DashboardPage({super.key});

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return BlocBuilder<ModelsBloc, ModelsState>(
      builder: (context, state) {
        final ok = state.hardwareStatus == Status.success;
        final gpus = state.gpus;
        final totalVram = gpus.fold<double>(0, (s, g) => s + g.totalGib);
        final usedVram = gpus.fold<double>(0, (s, g) => s + (g.totalGib - g.freeGib));

        return BlocBuilder<OverviewCubit, OverviewState>(
          builder: (context, overview) {
            final usage = overview.usage;
            final loaded = overview.loaded;
            final platform = overview.platform;
            return PageScaffold(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SectionHeader(
                    eyebrow: 'Inicio',
                    title: 'Tu IA, en tu equipo',
                    subtitle: 'Lo que Magnus sabe de este equipo y lo que llevas ahorrado.',
                    trailing: _DaemonStatus(state.hardwareStatus),
                  ),
                  _Hero(
                    platform: platform,
                    totalGib: totalVram,
                    usedGib: usedVram,
                    ready: ok,
                  ),
                  const SizedBox(height: 16),
                  TileGrid(
                    children: [
                      StatTile(
                        icon: context.icons.gpu,
                        label: platform?.familyLabel ?? 'GPUs',
                        value: ok ? '${gpus.length}' : '—',
                        tone: t.accent,
                        sub: gpus.length == 1 ? 'GPU detectada' : 'GPUs detectadas',
                      ),
                      StatTile(
                        icon: context.icons.memory,
                        label: platform?.unifiedMemory == true ? 'Memoria unificada' : 'VRAM total',
                        value: ok ? '${totalVram.toStringAsFixed(1)} GiB' : '—',
                        tone: t.info,
                        sub: ok ? '${usedVram.toStringAsFixed(1)} GiB en uso' : null,
                      ),
                      StatTile(
                        icon: context.icons.models,
                        label: 'Modelo en memoria',
                        value: loaded.isEmpty ? 'Ninguno' : '${loaded.length}',
                        tone: Brand.lilac,
                        sub: loaded.isEmpty
                            ? 'se carga al chatear'
                            : loaded.map((m) => m.modelId).join(', '),
                      ),
                      _AhorroTile(usage: usage),
                    ],
                  ),
                  const SizedBox(height: 16),
                  const CodeCapabilityCard(),
                  const SizedBox(height: 26),
                  const SubHeading('GPUs detectadas', eyebrow: 'Hardware'),
                  switch (state.hardwareStatus) {
                    Status.loading || Status.initial => const _Loading(),
                    Status.failure => _ErrorBox(state.failureMessage),
                    Status.success when gpus.isEmpty => const _NoGpu(),
                    Status.success => TileGrid(
                        minTileWidth: 320,
                        children: [for (final g in gpus) _GpuCard(g)],
                      ),
                  },
                ],
              ),
            );
          },
        );
      },
    );
  }
}

/// El ahorro acumulado, contado con honestidad.
///
/// Al principio suele ser **negativo**: amortizar el equipo durante medio minuto
/// cuesta más que los pocos tokens que habría cobrado la nube. En vez de enseñar
/// un número en rojo que parece un error, se dice qué está pasando; el ámbar de
/// la marca se reserva para cuando de verdad hay ahorro.
class _AhorroTile extends StatelessWidget {
  const _AhorroTile({required this.usage});

  final UsageSummary? usage;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final u = usage;
    if (u == null) {
      return StatTile(
        icon: context.icons.savings,
        label: 'Ahorro vs nube',
        value: '—',
        tone: Brand.amber,
      );
    }
    final ahorra = u.savingsUsd >= 0;
    return StatTile(
      icon: ahorra ? context.icons.savings : context.icons.activity,
      label: ahorra ? 'Ahorro vs nube' : 'Todavía no compensa',
      value: formatUsd(u.savingsUsd.abs()),
      tone: ahorra ? Brand.amber : t.textMuted,
      sub: ahorra
          ? '${u.turns} respuestas · ${u.tokensOut} tokens'
          : 'en turnos cortos pesa más amortizar el equipo',
    );
  }
}

/// Cabecera con aurora: la respuesta a «¿qué puede correr este equipo?».
class _Hero extends StatelessWidget {
  const _Hero({
    required this.platform,
    required this.totalGib,
    required this.usedGib,
    required this.ready,
  });
  final PlatformInfo? platform;
  final double totalGib;
  final double usedGib;
  final bool ready;

  static String _params(double b) =>
      b == b.roundToDouble() ? b.toStringAsFixed(0) : b.toStringAsFixed(1);

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final p = platform;
    final radius = BorderRadius.circular(t.radiusLg);
    final free = (totalGib - usedGib).clamp(0, totalGib).toDouble();
    final frac = totalGib > 0 ? usedGib / totalGib : 0.0;

    final summary = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('ESTE EQUIPO', style: t.eyebrow),
        const SizedBox(height: 10),
        Text(
          p == null
              ? 'Detectando tu hardware…'
              : 'Corre modelos de hasta ~${_params(p.suggestedMaxParamsB)} B',
          style: t.display.copyWith(fontSize: 32),
        ),
        const SizedBox(height: 8),
        if (p != null)
          Text(
            '${p.displayName} · cuantizados a 4 bits, con margen para el contexto.',
            style: t.body.copyWith(color: t.textMuted),
          ),
        const SizedBox(height: 16),
        if (p != null)
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              Pill(p.familyLabel, color: t.accent, icon: context.icons.gpu),
              for (final r in p.runtimes) Pill(r, color: t.info, icon: context.icons.bolt),
              Pill(
                p.maxLoadedModels == 1
                    ? '1 modelo a la vez'
                    : '${p.maxLoadedModels} modelos a la vez',
                color: t.textMuted,
                icon: context.icons.layers,
              ),
            ],
          ),
      ],
    );

    final memory = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(p?.unifiedMemory == true ? 'MEMORIA LIBRE' : 'VRAM LIBRE',
            style: t.eyebrow.copyWith(color: t.textFaint)),
        const SizedBox(height: 8),
        Text(ready ? '${free.toStringAsFixed(1)} GiB' : '—',
            style: t.numeral.copyWith(fontSize: 34)),
        const SizedBox(height: 12),
        UsageBar(fraction: frac, color: frac > 0.85 ? t.bad : t.accent, height: 6),
        const SizedBox(height: 8),
        Text(ready ? 'de ${totalGib.toStringAsFixed(1)} GiB' : 'sin datos', style: t.small),
      ],
    );

    return DecoratedBox(
      decoration: BoxDecoration(
        color: t.surface,
        borderRadius: radius,
        boxShadow: t.glass ? null : t.shadow,
      ),
      child: AuroraBackdrop(
        radius: radius,
        intensity: 0.8,
        child: Container(
          padding: const EdgeInsets.fromLTRB(26, 24, 26, 24),
          decoration: BoxDecoration(
            borderRadius: radius,
            border: Border.all(color: t.stroke),
          ),
          child: LayoutBuilder(
            builder: (context, c) => c.maxWidth < 640
                ? Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [summary, const SizedBox(height: 22), memory],
                  )
                : Row(
                    children: [
                      Expanded(child: summary),
                      const SizedBox(width: 28),
                      SizedBox(width: 220, child: memory),
                    ],
                  ),
          ),
        ),
      ),
    );
  }
}

class _DaemonStatus extends StatelessWidget {
  const _DaemonStatus(this.status);
  final Status status;
  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final (color, label) = switch (status) {
      Status.success => (t.ok, 'Daemon conectado'),
      Status.loading || Status.initial => (t.warn, 'Conectando…'),
      Status.failure => (t.bad, 'Sin conexión'),
    };
    return GlassCard(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          StatusDot(color),
          const SizedBox(width: 8),
          Text(label, style: t.small.copyWith(color: t.text)),
        ],
      ),
    );
  }
}

class _GpuCard extends StatelessWidget {
  const _GpuCard(this.gpu);
  final Gpu gpu;
  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final used = (gpu.totalGib - gpu.freeGib).clamp(0, gpu.totalGib);
    final frac = gpu.totalGib > 0 ? used / gpu.totalGib : 0.0;
    final pct = (frac * 100);
    final barColor = pct > 85 ? t.bad : (pct > 60 ? t.warn : t.ok);
    return GlassCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(context.icons.gpu, size: 16, color: t.accent),
                const SizedBox(width: 8),
                Text('GPU ${gpu.index}', style: t.small),
                const Spacer(),
                Pill('${pct.toStringAsFixed(0)}%', color: barColor),
              ],
            ),
            const SizedBox(height: 6),
            Text(gpu.name,
                style: t.h2, maxLines: 1, overflow: TextOverflow.ellipsis),
            const SizedBox(height: 16),
            UsageBar(fraction: frac.toDouble(), color: barColor),
            const SizedBox(height: 9),
            Text.rich(
              TextSpan(children: [
                TextSpan(text: used.toStringAsFixed(1), style: t.mono.copyWith(color: t.text)),
                TextSpan(
                    text: ' / ${gpu.totalGib.toStringAsFixed(1)} GiB en uso', style: t.small),
              ]),
            ),
          ],
        ),
      );
  }
}

class _Loading extends StatelessWidget {
  const _Loading();
  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return GlassCard(child: Text('Cargando hardware…', style: t.small));
  }
}

class _NoGpu extends StatelessWidget {
  const _NoGpu();
  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return GlassCard(
      child: Text(
        'No se detectó GPU NVIDIA en el host (o el daemon corre sin GPU).',
        style: t.body,
      ),
    );
  }
}

class _ErrorBox extends StatelessWidget {
  const _ErrorBox(this.message);
  final String? message;
  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: t.bad.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(t.radiusLg),
        border: Border.all(color: t.bad.withValues(alpha: 0.4)),
      ),
      child: Row(
        children: [
          Icon(context.icons.warning, color: t.bad, size: 18),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message ?? 'No se pudo cargar el hardware. ¿Está corriendo el daemon?',
              style: t.body.copyWith(color: t.bad),
            ),
          ),
        ],
      ),
    );
  }
}
