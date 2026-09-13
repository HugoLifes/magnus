import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/error/failures.dart';
import '../../../../core/network/api_models.dart';
import '../../../../core/network/magnus_api.dart';

class RagState extends Equatable {
  const RagState({
    this.collections = const [],
    this.selected,
    this.documents = const [],
    this.hits = const [],
    this.memories = const [],
    this.lastIngest,
    this.busy = false,
    this.busyLabel,
    this.error,
  });

  final List<CollectionInfo> collections;
  final String? selected;
  final List<DocumentInfo> documents;
  final List<SearchHit> hits;
  final List<MemoryItem> memories;
  final IngestResult? lastIngest;
  final bool busy;
  final String? busyLabel;
  final String? error;

  CollectionInfo? get selectedCollection =>
      collections.where((c) => c.name == selected).firstOrNull;

  RagState copyWith({
    List<CollectionInfo>? collections,
    String? selected,
    List<DocumentInfo>? documents,
    List<SearchHit>? hits,
    List<MemoryItem>? memories,
    IngestResult? lastIngest,
    bool clearIngest = false,
    bool? busy,
    String? busyLabel,
    String? error,
  }) =>
      RagState(
        collections: collections ?? this.collections,
        selected: selected ?? this.selected,
        documents: documents ?? this.documents,
        hits: hits ?? this.hits,
        memories: memories ?? this.memories,
        lastIngest: clearIngest ? null : (lastIngest ?? this.lastIngest),
        busy: busy ?? this.busy,
        busyLabel: busyLabel,
        error: error,
      );

  @override
  List<Object?> get props =>
      [collections, selected, documents, hits, memories, lastIngest, busy, busyLabel, error];
}

/// Documentos (colecciones del RAG local) y memoria de hechos del usuario.
class RagCubit extends Cubit<RagState> {
  RagCubit(this._api) : super(const RagState());

  final MagnusApi _api;

  Future<void> _run(String label, Future<void> Function() action) async {
    emit(state.copyWith(busy: true, busyLabel: label));
    try {
      await action();
      emit(state.copyWith(busy: false));
    } on Failure catch (f) {
      emit(state.copyWith(busy: false, error: f.message));
    }
  }

  Future<void> load() => _run('Cargando…', () async {
        final collections = await _api.collections();
        final memories = await _api.memories();
        final selected = collections.any((c) => c.name == state.selected)
            ? state.selected
            : (collections.isEmpty ? null : collections.first.name);
        emit(state.copyWith(collections: collections, memories: memories, selected: selected));
        if (selected != null) {
          emit(state.copyWith(documents: await _api.documents(selected)));
        }
      });

  Future<void> select(String name) => _run('Cargando documentos…', () async {
        emit(state.copyWith(selected: name, hits: const [], clearIngest: true));
        emit(state.copyWith(documents: await _api.documents(name)));
      });

  Future<void> create(String name, String embeddingModel, int chunkChars, int overlapChars) =>
      _run('Creando colección…', () async {
        await _api.createCollection(name,
            embeddingModel: embeddingModel, chunkChars: chunkChars, overlapChars: overlapChars);
        emit(state.copyWith(selected: name));
        await load();
      });

  Future<void> deleteCollection(String name) => _run('Borrando…', () async {
        await _api.deleteCollection(name);
        await load();
      });

  /// Indexa rutas de la máquina del daemon y/o un texto pegado.
  Future<void> ingest({List<String> paths = const [], String? text}) async {
    final name = state.selected;
    if (name == null) return;
    await _run('Indexando (calcula embeddings, puede tardar)…', () async {
      final result = await _api.ingest(name, paths: paths, text: text);
      emit(state.copyWith(lastIngest: result));
      await load();
    });
  }

  Future<void> search(String query) async {
    final name = state.selected;
    if (name == null || query.trim().isEmpty) return;
    await _run('Buscando…', () async {
      emit(state.copyWith(hits: await _api.search(name, query)));
    });
  }

  Future<void> addMemory(String text) => _run('Guardando…', () async {
        await _api.addMemory(text);
        emit(state.copyWith(memories: await _api.memories()));
      });

  Future<void> deleteMemory(int id) => _run('Olvidando…', () async {
        await _api.deleteMemory(id);
        emit(state.copyWith(memories: await _api.memories()));
      });

  void dismiss() => emit(state.copyWith());
}
