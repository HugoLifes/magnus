import 'package:flutter/material.dart'
    show Material, Colors, TextField, InputDecoration, OutlineInputBorder, Icons, Slider;
import 'package:flutter/widgets.dart';

import '../../../../core/theme/magnus_theme.dart';
import '../../../../shared/widgets/ui.dart';

/// Sección RAG: configurar y levantar el mini-RAG local (sqlite-vec +
/// embeddings locales). La construcción del índice se conectará al daemon
/// (Fase 1, `[3.4]`); aquí queda toda la configuración lista.
class RagPage extends StatefulWidget {
  const RagPage({super.key});
  @override
  State<RagPage> createState() => _RagPageState();
}

class _RagPageState extends State<RagPage> {
  final _collection = TextEditingController(text: 'mi-coleccion');
  final _sourceCtrl = TextEditingController();
  final List<String> _sources = ['D:\\docs\\manual.pdf'];
  String _embModel = 'nomic-embed-text';
  double _chunkSize = 512;
  double _overlap = 64;

  static const _embModels = [
    'nomic-embed-text',
    'bge-small-en',
    'all-MiniLM-L6-v2',
    'e5-large-v2',
  ];

  @override
  void dispose() {
    _collection.dispose();
    _sourceCtrl.dispose();
    super.dispose();
  }

  void _addSource() {
    final s = _sourceCtrl.text.trim();
    if (s.isEmpty) return;
    setState(() {
      _sources.add(s);
      _sourceCtrl.clear();
    });
  }

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return Material(
      color: Colors.transparent,
      child: PageScaffold(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SectionHeader(
              icon: Icons.hub_rounded,
              title: 'RAG local',
              subtitle: 'Memoria extendida: indexa tus fuentes con embeddings locales.',
              trailing: Pill('índice no construido', color: t.warn),
            ),

            // --- Colección + embeddings ---
            GlassCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Colección', style: t.h2),
                  const SizedBox(height: 12),
                  _Field(controller: _collection, hint: 'nombre-de-coleccion'),
                  const SizedBox(height: 18),
                  Text('Modelo de embeddings', style: t.h2),
                  const SizedBox(height: 4),
                  Text('Corre localmente en el servidor de Magnus.', style: t.small),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      for (final m in _embModels)
                        _Chip(
                          label: m,
                          selected: m == _embModel,
                          onTap: () => setState(() => _embModel = m),
                        ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // --- Fuentes ---
            GlassCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Fuentes', style: t.h2),
                  const SizedBox(height: 4),
                  Text('Archivos, carpetas o URLs a indexar.', style: t.small),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _Field(
                          controller: _sourceCtrl,
                          hint: 'Ruta o URL…',
                          onSubmit: (_) => _addSource(),
                        ),
                      ),
                      const SizedBox(width: 10),
                      MagnusButton(
                        label: 'Añadir',
                        icon: Icons.add_rounded,
                        primary: false,
                        onTap: _addSource,
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  for (final s in _sources)
                    Container(
                      margin: const EdgeInsets.only(bottom: 6),
                      padding: const EdgeInsets.symmetric(
                          horizontal: 12, vertical: 9),
                      decoration: BoxDecoration(
                        color: t.surfaceAlt,
                        borderRadius: BorderRadius.circular(t.radius),
                      ),
                      child: Row(
                        children: [
                          Icon(Icons.insert_drive_file_outlined,
                              size: 15, color: t.textMuted),
                          const SizedBox(width: 10),
                          Expanded(
                              child: Text(s,
                                  style: t.body,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis)),
                          GestureDetector(
                            onTap: () => setState(() => _sources.remove(s)),
                            child: Icon(Icons.close_rounded,
                                size: 16, color: t.textFaint),
                          ),
                        ],
                      ),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // --- Chunking ---
            GlassCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Segmentación (chunking)', style: t.h2),
                  const SizedBox(height: 14),
                  _SliderRow(
                    label: 'Tamaño de chunk',
                    value: _chunkSize,
                    min: 128,
                    max: 2048,
                    unit: 'tokens',
                    onChanged: (v) => setState(() => _chunkSize = v),
                  ),
                  const SizedBox(height: 10),
                  _SliderRow(
                    label: 'Solapamiento',
                    value: _overlap,
                    min: 0,
                    max: 256,
                    unit: 'tokens',
                    onChanged: (v) => setState(() => _overlap = v),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),

            Row(
              children: [
                MagnusButton(
                  label: 'Construir índice',
                  icon: Icons.build_rounded,
                  onTap: () {}, // pendiente: endpoint RAG del daemon (Fase 1)
                ),
                const SizedBox(width: 12),
                Text('Se ejecuta en el servidor; no bloquea la app.',
                    style: t.small),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _Field extends StatelessWidget {
  const _Field({required this.controller, required this.hint, this.onSubmit});
  final TextEditingController controller;
  final String hint;
  final ValueChanged<String>? onSubmit;
  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return TextField(
      controller: controller,
      style: TextStyle(color: t.text, fontSize: 13.5),
      onSubmitted: onSubmit,
      decoration: InputDecoration(
        isDense: true,
        filled: true,
        fillColor: t.surfaceAlt,
        hintText: hint,
        hintStyle: TextStyle(color: t.textFaint),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(t.radius),
          borderSide: BorderSide(color: t.stroke),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(t.radius),
          borderSide: BorderSide(color: t.stroke),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(t.radius),
          borderSide: BorderSide(color: t.accent),
        ),
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  const _Chip(
      {required this.label, required this.selected, required this.onTap});
  final String label;
  final bool selected;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 8),
        decoration: BoxDecoration(
          color: selected ? t.accent : t.surfaceAlt,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: selected ? t.accent : t.stroke),
        ),
        child: Text(label,
            style: TextStyle(
                fontSize: 12.5,
                fontWeight: FontWeight.w600,
                color: selected ? t.onAccent : t.textMuted)),
      ),
    );
  }
}

class _SliderRow extends StatelessWidget {
  const _SliderRow({
    required this.label,
    required this.value,
    required this.min,
    required this.max,
    required this.unit,
    required this.onChanged,
  });
  final String label;
  final double value;
  final double min;
  final double max;
  final String unit;
  final ValueChanged<double> onChanged;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return Row(
      children: [
        SizedBox(width: 150, child: Text(label, style: t.body)),
        Expanded(
          child: Slider(
            value: value,
            min: min,
            max: max,
            activeColor: t.accent,
            inactiveColor: t.surfaceAlt,
            onChanged: onChanged,
          ),
        ),
        SizedBox(
          width: 96,
          child: Text('${value.toStringAsFixed(0)} $unit',
              textAlign: TextAlign.right, style: t.small.copyWith(color: t.text)),
        ),
      ],
    );
  }
}
