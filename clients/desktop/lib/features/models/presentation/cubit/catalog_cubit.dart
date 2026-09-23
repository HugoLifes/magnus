import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/error/failures.dart';
import '../../../../core/network/api_models.dart';
import '../../../../core/network/magnus_api.dart';

class CatalogState extends Equatable {
  const CatalogState({
    this.catalog,
    this.local = const [],
    this.loaded = const [],
    this.capability,
    this.pulls = const {},
    this.busy = const {},
    this.loading = false,
    this.notice,
    this.error,
  });

  final CatalogInfo? catalog;
  final List<LocalModel> local;
  final List<LoadedModel> loaded;
  final String? capability;

  /// Descargas en curso por modelo.
  final Map<String, PullProgress> pulls;

  /// Modelos con una operación en curso (cargar, liberar, borrar).
  final Set<String> busy;
  final bool loading;
  final String? notice;
  final String? error;

  bool isLocal(String id) => local.any((m) => m.modelId == id || m.modelId == '$id:latest');
  bool isLoaded(String id) => loaded.any((m) => m.modelId == id || m.modelId == '$id:latest');

  CatalogState copyWith({
    CatalogInfo? catalog,
    List<LocalModel>? local,
    List<LoadedModel>? loaded,
    String? capability,
    bool clearCapability = false,
    Map<String, PullProgress>? pulls,
    Set<String>? busy,
    bool? loading,
    String? notice,
    String? error,
  }) =>
      CatalogState(
        catalog: catalog ?? this.catalog,
        local: local ?? this.local,
        loaded: loaded ?? this.loaded,
        capability: clearCapability ? null : (capability ?? this.capability),
        pulls: pulls ?? this.pulls,
        busy: busy ?? this.busy,
        loading: loading ?? this.loading,
        notice: notice,
        error: error,
      );

  @override
  List<Object?> get props =>
      [catalog, local, loaded, capability, pulls, busy, loading, notice, error];
}

/// Modelos para ESTE equipo: catálogo con veredicto de memoria, descargas con
/// progreso y carga/liberación con la guarda de memoria del daemon.
class CatalogCubit extends Cubit<CatalogState> {
  CatalogCubit(this._api) : super(const CatalogState());

  final MagnusApi _api;

  Future<void> load() async {
    emit(state.copyWith(loading: true));
    try {
      final results = await Future.wait([
        _api.catalog(capability: state.capability),
        _api.localModels(),
        _api.loadedModels(),
      ]);
      emit(state.copyWith(
        loading: false,
        catalog: results[0] as CatalogInfo,
        local: results[1] as List<LocalModel>,
        loaded: results[2] as List<LoadedModel>,
      ));
    } on Failure catch (f) {
      emit(state.copyWith(loading: false, error: f.message));
    }
  }

  Future<void> setCapability(String? capability) async {
    emit(capability == null
        ? state.copyWith(clearCapability: true)
        : state.copyWith(capability: capability));
    await load();
  }

  Future<void> pull(String id) async {
    if (state.pulls.containsKey(id)) return;
    emit(state.copyWith(pulls: {...state.pulls, id: const PullProgress(status: 'iniciando')}));
    String? error;
    try {
      await for (final p in _api.pullModel(id)) {
        if (p.isError) {
          error = p.detail;
          break;
        }
        emit(state.copyWith(pulls: {...state.pulls, id: p}));
      }
    } on Failure catch (f) {
      error = f.message;
    }
    final pulls = {...state.pulls}..remove(id);
    emit(state.copyWith(
        pulls: pulls, error: error, notice: error == null ? '$id descargado.' : null));
    await load();
  }

  Future<void> _busy(String id, Future<String?> Function() action) async {
    emit(state.copyWith(busy: {...state.busy, id}));
    String? notice;
    String? error;
    try {
      notice = await action();
    } on Failure catch (f) {
      error = f.message;
    }
    emit(state.copyWith(busy: {...state.busy}..remove(id), notice: notice, error: error));
    await load();
  }

  Future<void> loadModel(String id, {bool force = false}) => _busy(id, () async {
        final loaded = await _api.loadModel(id, force: force);
        final size = loaded.sizeVramGib == null ? '' : ' (${loaded.sizeVramGib} GiB)';
        return ['$id cargado$size.', ...loaded.notes].join(' ');
      });

  Future<void> unloadModel(String id) => _busy(id, () async {
        await _api.unloadModel(id);
        return '$id liberado de la memoria.';
      });

  Future<void> deleteModel(String id) => _busy(id, () async {
        await _api.deleteModel(id);
        return '$id borrado del disco.';
      });

  void dismiss() => emit(state.copyWith());
}
