import 'package:flutter/widgets.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../../core/network/api_models.dart';
import '../../../../core/theme/magnus_theme.dart';
import '../../../../shared/widgets/forms.dart';
import '../../../../shared/widgets/ui.dart';
import '../cubit/rag_cubit.dart';

const _embeddingModels = ['nomic-embed-text', 'bge-m3'];

/// Documentos: colecciones del RAG local (indexar, buscar) y la memoria de
/// hechos que Magnus recuerda del usuario. Todo se calcula en el daemon.
class RagPage extends StatefulWidget {
  const RagPage({super.key});
  @override
  State<RagPage> createState() => _RagPageState();
}

class _RagPageState extends State<RagPage> {
  final _newName = TextEditingController();
  final _paths = TextEditingController();
  final _text = TextEditingController();
  final _query = TextEditingController();
  final _memory = TextEditingController();
  String _embedding = _embeddingModels.first;
  double _chunk = 1000;
  double _overlap = 150;
  bool _showCreate = false;

  @override
  void initState() {
    super.initState();
    context.read<RagCubit>().load();
  }

  @override
  void dispose() {
    for (final c in [_newName, _paths, _text, _query, _memory]) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return BlocBuilder<RagCubit, RagState>(
      builder: (context, state) {
        final cubit = context.read<RagCubit>();
        final selected = state.selectedCollection;
        return PageScaffold(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SectionHeader(
                icon: LucideIcons.brain,
                title: 'Documentos y memoria',
                subtitle: 'Indexa tus archivos para que el chat y los agentes respondan con tus datos.',
                trailing: state.busy && state.busyLabel != null
                    ? Pill(state.busyLabel!, color: t.warn)
                    : null,
              ),
              if (state.error != null) ...[
                InlineNotice(state.error!, onClose: cubit.dismiss),
                const SizedBox(height: 14),
              ],

              // --- Colecciones ---
              GlassCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(child: Text('Colecciones', style: t.h2)),
                        MagnusButton(
                          label: _showCreate ? 'Cancelar' : 'Nueva colección',
                          icon: _showCreate ? LucideIcons.x : LucideIcons.folderPlus,
                          primary: !_showCreate,
                          dense: true,
                          onTap: () => setState(() => _showCreate = !_showCreate),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    if (_showCreate) ...[
                      _CreateForm(
                        name: _newName,
                        embedding: _embedding,
                        chunk: _chunk,
                        overlap: _overlap,
                        onEmbedding: (v) => setState(() => _embedding = v),
                        onChunk: (v) => setState(() => _chunk = v),
                        onOverlap: (v) => setState(() => _overlap = v.clamp(0, _chunk / 2)),
                        onCreate: state.busy
                            ? null
                            : () {
                                final name = _newName.text.trim();
                                if (name.isEmpty) return;
                                cubit.create(name, _embedding, _chunk.round(), _overlap.round());
                                _newName.clear();
                                setState(() => _showCreate = false);
                              },
                      ),
                      const SizedBox(height: 14),
                    ],
                    if (state.collections.isEmpty)
                      Text('Crea una colección y añade tus documentos.', style: t.small)
                    else
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          for (final c in state.collections)
                            ChoiceChipX(
                              label: '${c.name} · ${c.documents} docs',
                              icon: LucideIcons.bookOpen,
                              selected: c.name == state.selected,
                              onTap: () => cubit.select(c.name),
                            ),
                        ],
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              if (selected != null) ...[
                _CollectionDetail(
                  collection: selected,
                  state: state,
                  paths: _paths,
                  text: _text,
                  query: _query,
                ),
                const SizedBox(height: 16),
              ],

              // --- Memoria ---
              GlassCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Memoria', style: t.h2),
                    const SizedBox(height: 4),
                    Text(
                        'Hechos cortos sobre ti. El chat los usa solo si lo pides en equipos donde '
                        'cabe un único modelo (así no se descarga el de chat en cada mensaje).',
                        style: t.small),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: MagnusTextField(
                            controller: _memory,
                            hint: 'p. ej. Trabajo con un Jetson Orin Nano',
                            onSubmitted: (_) => _addMemory(cubit),
                          ),
                        ),
                        const SizedBox(width: 10),
                        MagnusButton(
                          label: 'Recordar',
                          icon: LucideIcons.plus,
                          onTap: state.busy ? null : () => _addMemory(cubit),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    for (final m in state.memories)
                      _Row(
                        icon: LucideIcons.lightbulb,
                        text: m.text,
                        onDelete: () => cubit.deleteMemory(m.id),
                      ),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  void _addMemory(RagCubit cubit) {
    final text = _memory.text.trim();
    if (text.isEmpty) return;
    cubit.addMemory(text);
    _memory.clear();
  }
}

class _CreateForm extends StatelessWidget {
  const _CreateForm({
    required this.name,
    required this.embedding,
    required this.chunk,
    required this.overlap,
    required this.onEmbedding,
    required this.onChunk,
    required this.onOverlap,
    required this.onCreate,
  });

  final TextEditingController name;
  final String embedding;
  final double chunk;
  final double overlap;
  final ValueChanged<String> onEmbedding;
  final ValueChanged<double> onChunk;
  final ValueChanged<double> onOverlap;
  final VoidCallback? onCreate;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: t.surfaceAlt,
        borderRadius: BorderRadius.circular(t.radius),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const FieldLabel('Nombre'),
          MagnusTextField(controller: name, hint: 'manuales, contratos, código…'),
          const SizedBox(height: 14),
          const FieldLabel('Modelo de embeddings',
              hint: 'Corre en local. bge-m3 es mejor en español; nomic-embed-text, más ligero.'),
          Wrap(
            spacing: 8,
            children: [
              for (final m in _embeddingModels)
                ChoiceChipX(label: m, selected: m == embedding, onTap: () => onEmbedding(m)),
            ],
          ),
          const SizedBox(height: 14),
          SliderField(
              label: 'Tamaño de fragmento', value: chunk, min: 300, max: 3000, divisions: 27,
              unit: 'car.', onChanged: onChunk),
          SliderField(
              label: 'Solapamiento', value: overlap, min: 0, max: 600, divisions: 24,
              unit: 'car.', onChanged: onOverlap),
          const SizedBox(height: 8),
          MagnusButton(label: 'Crear colección', icon: LucideIcons.check, onTap: onCreate),
        ],
      ),
    );
  }
}

class _CollectionDetail extends StatelessWidget {
  const _CollectionDetail({
    required this.collection,
    required this.state,
    required this.paths,
    required this.text,
    required this.query,
  });

  final CollectionInfo collection;
  final RagState state;
  final TextEditingController paths;
  final TextEditingController text;
  final TextEditingController query;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final cubit = context.read<RagCubit>();
    final ingest = state.lastIngest;
    return GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: Text(collection.name, style: t.h1)),
              Pill('${collection.chunks} fragmentos', color: t.info),
              const SizedBox(width: 8),
              Pill(collection.embeddingModel, color: t.accent),
              const SizedBox(width: 8),
              MagnusButton(
                label: 'Borrar',
                icon: LucideIcons.trash2,
                primary: false,
                dense: true,
                onTap: state.busy ? null : () => cubit.deleteCollection(collection.name),
              ),
            ],
          ),
          const SizedBox(height: 16),
          const FieldLabel('Añadir archivos o carpetas',
              hint: 'Rutas de la máquina donde corre el daemon, una por línea. '
                  'txt, md, código, html, csv, json y PDF.'),
          MagnusTextField(controller: paths, hint: r'D:\documentos\manuales', minLines: 2, maxLines: 5, mono: true),
          const SizedBox(height: 12),
          const FieldLabel('…o pega un texto'),
          MagnusTextField(controller: text, hint: 'Texto a indexar', minLines: 3, maxLines: 8),
          const SizedBox(height: 12),
          Row(
            children: [
              MagnusButton(
                label: 'Indexar',
                icon: LucideIcons.hammer,
                onTap: state.busy
                    ? null
                    : () {
                        final list = paths.text
                            .split('\n')
                            .map((p) => p.trim())
                            .where((p) => p.isNotEmpty)
                            .toList();
                        final pasted = text.text.trim();
                        if (list.isEmpty && pasted.isEmpty) return;
                        cubit.ingest(paths: list, text: pasted.isEmpty ? null : pasted);
                        paths.clear();
                        text.clear();
                      },
              ),
              const SizedBox(width: 12),
              if (ingest != null)
                Expanded(
                  child: Text(
                    '${ingest.indexed} nuevos · ${ingest.skipped} ya estaban · ${ingest.chunks} fragmentos',
                    style: t.small.copyWith(color: t.ok),
                  ),
                ),
            ],
          ),
          if (ingest != null)
            for (final e in ingest.errors.entries) ...[
              const SizedBox(height: 6),
              InlineNotice('${e.key}: ${e.value}', kind: NoticeKind.warning),
            ],
          const SizedBox(height: 18),
          Text('Documentos', style: t.h2),
          const SizedBox(height: 8),
          if (state.documents.isEmpty) Text('Sin documentos todavía.', style: t.small),
          for (final d in state.documents)
            _Row(icon: LucideIcons.fileText, text: '${d.title} · ${d.chunks} fragmentos'),
          const SizedBox(height: 18),
          Text('Probar búsqueda', style: t.h2),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: MagnusTextField(
                  controller: query,
                  hint: '¿Qué quieres encontrar?',
                  onSubmitted: (v) => cubit.search(v),
                ),
              ),
              const SizedBox(width: 10),
              MagnusButton(
                label: 'Buscar',
                icon: LucideIcons.search,
                primary: false,
                onTap: state.busy ? null : () => cubit.search(query.text),
              ),
            ],
          ),
          const SizedBox(height: 10),
          for (final h in state.hits)
            Container(
              margin: const EdgeInsets.only(bottom: 8),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: t.surfaceAlt,
                borderRadius: BorderRadius.circular(t.radius),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(child: Text(h.title, style: t.body.copyWith(fontWeight: FontWeight.w600))),
                      Pill(h.score.toStringAsFixed(3), color: t.info),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(h.text, style: t.small, maxLines: 5, overflow: TextOverflow.ellipsis),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.icon, required this.text, this.onDelete});
  final IconData icon;
  final String text;
  final VoidCallback? onDelete;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
      decoration: BoxDecoration(
        color: t.surfaceAlt,
        borderRadius: BorderRadius.circular(t.radius),
      ),
      child: Row(
        children: [
          Icon(icon, size: 15, color: t.textMuted),
          const SizedBox(width: 10),
          Expanded(child: Text(text, style: t.body, maxLines: 2, overflow: TextOverflow.ellipsis)),
          if (onDelete != null)
            GestureDetector(
              onTap: onDelete,
              child: MouseRegion(
                cursor: SystemMouseCursors.click,
                child: Icon(LucideIcons.x, size: 14, color: t.textFaint),
              ),
            ),
        ],
      ),
    );
  }
}
