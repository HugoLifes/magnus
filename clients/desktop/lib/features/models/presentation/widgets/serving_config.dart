import 'package:flutter/material.dart' show Material, Colors, Slider, Switch;
import 'package:flutter/widgets.dart';
import '../../../../core/theme/icons.dart';

import '../../../../core/theme/magnus_theme.dart';
import '../../../../shared/widgets/ui.dart';
import '../../domain/entities.dart';

/// Vendor de GPU detectado (decide el stack de serving recomendado).
enum GpuVendor {
  nvidia('NVIDIA', 'TensorRT-LLM o vLLM'),
  amd('AMD', 'vLLM (ROCm)'),
  other('Otro / CPU', 'vLLM o Ollama');

  const GpuVendor(this.label, this.hint);
  final String label;
  final String hint;
}

/// Heurística para inferir el vendor a partir del nombre de la GPU del daemon.
GpuVendor detectVendor(List<Gpu> gpus) {
  if (gpus.isEmpty) return GpuVendor.other;
  final n = gpus.first.name.toLowerCase();
  const nvidia = [
    'nvidia', 'geforce', 'rtx', 'gtx', 'tesla', 'quadro',
    'a100', 'h100', 'h200', 'b200', 'gb200', 'l40', 'spark', 'dgx',
  ];
  const amd = ['amd', 'radeon', 'instinct', 'mi200', 'mi250', 'mi300', 'rocm'];
  if (nvidia.any(n.contains)) return GpuVendor.nvidia;
  if (amd.any(n.contains)) return GpuVendor.amd;
  return GpuVendor.other;
}

List<String> runtimesFor(GpuVendor v) => switch (v) {
      GpuVendor.nvidia => const ['TensorRT-LLM', 'vLLM', 'Ollama'],
      GpuVendor.amd => const ['vLLM', 'Ollama'],
      GpuVendor.other => const ['vLLM', 'Ollama'],
    };

/// Panel de configuración de serving: autodetecta vendor + runtime y deja al
/// usuario afinar las variables de optimización. Los valores alimentarán al
/// daemon (`/serve`) cuando exista (Fase 1). Estado local por ahora.
class ServingConfigCard extends StatefulWidget {
  const ServingConfigCard({super.key, required this.gpus});
  final List<Gpu> gpus;

  @override
  State<ServingConfigCard> createState() => _ServingConfigCardState();
}

class _ServingConfigCardState extends State<ServingConfigCard> {
  GpuVendor? _vendorOverride; // null = usar autodetección
  String? _runtimeOverride;
  double _maxModelLen = 8192;
  double _maxTokens = 2048;
  int _tensorParallel = 1;
  double _gpuMemUtil = 0.90;
  bool _flashInfer = true;
  String _kvCacheDtype = 'auto';

  GpuVendor get _vendor => _vendorOverride ?? detectVendor(widget.gpus);
  String get _runtime => _runtimeOverride ?? runtimesFor(_vendor).first;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final autodetected = _vendorOverride == null;
    final gpuCount = widget.gpus.isEmpty ? 1 : widget.gpus.length;
    if (_tensorParallel > gpuCount) _tensorParallel = gpuCount;

    return Material(
      color: Colors.transparent,
      child: GlassCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(context.icons.tune, size: 16, color: t.accent),
                const SizedBox(width: 8),
                Text('Configuración de serving', style: t.h2),
                const Spacer(),
                if (autodetected)
                  Pill('autodetectado', color: t.ok, icon: context.icons.sparkle),
              ],
            ),
            const SizedBox(height: 4),
            Text(
                'Hardware: ${widget.gpus.isEmpty ? "sin GPU detectada" : widget.gpus.first.name}',
                style: t.small),
            const SizedBox(height: 16),

            // Vendor
            _Label('Vendor de GPU', hint: _vendor.hint),
            const SizedBox(height: 8),
            _Seg<GpuVendor>(
              options: GpuVendor.values,
              value: _vendor,
              labelOf: (v) => v.label,
              onTap: (v) => setState(() {
                _vendorOverride = v;
                _runtimeOverride = null; // re-sugiere runtime
              }),
            ),
            const SizedBox(height: 16),

            // Runtime
            const _Label('Runtime de inferencia'),
            const SizedBox(height: 8),
            _Seg<String>(
              options: runtimesFor(_vendor),
              value: _runtime,
              labelOf: (s) => s,
              onTap: (s) => setState(() => _runtimeOverride = s),
            ),
            const SizedBox(height: 18),

            // Sliders
            _SliderRow(
              label: 'Longitud máx. de contexto',
              value: _maxModelLen,
              min: 2048,
              max: 131072,
              divisions: 63,
              unit: 'tok',
              onChanged: (v) => setState(() => _maxModelLen = v),
            ),
            _SliderRow(
              label: 'Máx. tokens de salida',
              value: _maxTokens,
              min: 256,
              max: 16384,
              divisions: 63,
              unit: 'tok',
              onChanged: (v) => setState(() => _maxTokens = v),
            ),
            _SliderRow(
              label: 'Uso de memoria GPU',
              value: _gpuMemUtil,
              min: 0.50,
              max: 0.98,
              divisions: 48,
              unit: '%',
              percent: true,
              onChanged: (v) => setState(() => _gpuMemUtil = v),
            ),
            const SizedBox(height: 6),

            // Tensor parallel (stepper)
            Row(
              children: [
                SizedBox(
                    width: 170,
                    child: Text('Tensor parallel (GPUs)', style: t.body)),
                _Stepper(
                  value: _tensorParallel,
                  min: 1,
                  max: gpuCount,
                  onChanged: (v) => setState(() => _tensorParallel = v),
                ),
                const Spacer(),
                Text('de $gpuCount disponibles', style: t.small),
              ],
            ),
            const SizedBox(height: 14),

            // KV cache dtype
            const _Label('Precisión de KV cache'),
            const SizedBox(height: 8),
            _Seg<String>(
              options: const ['auto', 'fp16', 'fp8'],
              value: _kvCacheDtype,
              labelOf: (s) => s,
              onTap: (s) => setState(() => _kvCacheDtype = s),
            ),
            const SizedBox(height: 10),

            // FlashInfer toggle
            _ToggleRow(
              label: 'FlashInfer',
              hint: 'Kernels de atención optimizados (NVIDIA).',
              value: _flashInfer,
              enabled: _vendor == GpuVendor.nvidia,
              onChanged: (v) => setState(() => _flashInfer = v),
            ),
            const SizedBox(height: 18),

            Row(
              children: [
                // Solo Ollama está conectado en la beta; esta configuración es
                // para vLLM / TensorRT-LLM, que llegan después.
                MagnusButton(
                  label: 'Próximamente (vLLM)',
                  icon: context.icons.launch,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    '$_runtime · ctx ${_maxModelLen.toStringAsFixed(0)} · '
                    'tp$_tensorParallel · mem ${(_gpuMemUtil * 100).toStringAsFixed(0)}%'
                    '${_flashInfer && _vendor == GpuVendor.nvidia ? " · flashinfer" : ""}',
                    style: t.small,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _Label extends StatelessWidget {
  const _Label(this.text, {this.hint});
  final String text;
  final String? hint;
  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return Row(
      children: [
        Text(text, style: t.body.copyWith(fontWeight: FontWeight.w600)),
        if (hint != null) ...[
          const SizedBox(width: 8),
          Flexible(
            child: Text(hint!,
                style: t.small.copyWith(color: t.textFaint),
                overflow: TextOverflow.ellipsis),
          ),
        ],
      ],
    );
  }
}

class _Seg<T> extends StatelessWidget {
  const _Seg({
    required this.options,
    required this.value,
    required this.labelOf,
    required this.onTap,
  });
  final List<T> options;
  final T value;
  final String Function(T) labelOf;
  final ValueChanged<T> onTap;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        for (final o in options)
          GestureDetector(
            onTap: () => onTap(o),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 8),
              decoration: BoxDecoration(
                color: o == value ? t.accent : t.surfaceAlt,
                borderRadius: BorderRadius.circular(t.radius),
                border: Border.all(color: o == value ? t.accent : t.stroke),
              ),
              child: Text(labelOf(o),
                  style: TextStyle(
                      fontSize: 12.5,
                      fontWeight: FontWeight.w600,
                      color: o == value ? t.onAccent : t.textMuted)),
            ),
          ),
      ],
    );
  }
}

class _SliderRow extends StatelessWidget {
  const _SliderRow({
    required this.label,
    required this.value,
    required this.min,
    required this.max,
    required this.onChanged,
    required this.unit,
    this.divisions,
    this.percent = false,
  });
  final String label;
  final double value;
  final double min;
  final double max;
  final int? divisions;
  final String unit;
  final bool percent;
  final ValueChanged<double> onChanged;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final shown = percent
        ? '${(value * 100).toStringAsFixed(0)} $unit'
        : '${value.toStringAsFixed(0)} $unit';
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          SizedBox(width: 170, child: Text(label, style: t.body)),
          Expanded(
            child: Slider(
              value: value,
              min: min,
              max: max,
              divisions: divisions,
              activeColor: t.accent,
              inactiveColor: t.surfaceAlt,
              onChanged: onChanged,
            ),
          ),
          SizedBox(
            width: 92,
            child: Text(shown,
                textAlign: TextAlign.right,
                style: t.small.copyWith(color: t.text)),
          ),
        ],
      ),
    );
  }
}

class _Stepper extends StatelessWidget {
  const _Stepper({
    required this.value,
    required this.min,
    required this.max,
    required this.onChanged,
  });
  final int value;
  final int min;
  final int max;
  final ValueChanged<int> onChanged;
  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    Widget btn(IconData icon, VoidCallback? onTap) => GestureDetector(
          onTap: onTap,
          child: Container(
            width: 30,
            height: 30,
            decoration: BoxDecoration(
              color: t.surfaceAlt,
              borderRadius: BorderRadius.circular(t.radius),
              border: Border.all(color: t.stroke),
            ),
            child:
                Icon(icon, size: 16, color: onTap == null ? t.textFaint : t.text),
          ),
        );
    return Row(
      children: [
        btn(context.icons.minus, value > min ? () => onChanged(value - 1) : null),
        SizedBox(
          width: 34,
          child: Text('$value',
              textAlign: TextAlign.center,
              style: t.body.copyWith(fontWeight: FontWeight.w700)),
        ),
        btn(context.icons.add, value < max ? () => onChanged(value + 1) : null),
      ],
    );
  }
}

class _ToggleRow extends StatelessWidget {
  const _ToggleRow({
    required this.label,
    required this.hint,
    required this.value,
    required this.onChanged,
    this.enabled = true,
  });
  final String label;
  final String hint;
  final bool value;
  final bool enabled;
  final ValueChanged<bool> onChanged;
  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return Opacity(
      opacity: enabled ? 1 : 0.5,
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label,
                    style: t.body.copyWith(fontWeight: FontWeight.w600)),
                Text(hint, style: t.small),
              ],
            ),
          ),
          Switch(
            value: value && enabled,
            activeThumbColor: t.onAccent,
            activeTrackColor: t.accent,
            inactiveThumbColor: t.textMuted,
            inactiveTrackColor: t.surfaceAlt,
            onChanged: enabled ? onChanged : null,
          ),
        ],
      ),
    );
  }
}
