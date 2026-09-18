import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/error/failures.dart';
import '../../../../core/network/api_models.dart';
import '../../../../core/network/magnus_api.dart';

class OverviewState extends Equatable {
  const OverviewState({this.platform, this.usage, this.loaded = const [], this.health, this.error});

  final PlatformInfo? platform;
  final UsageSummary? usage;
  final List<LoadedModel> loaded;
  final HealthInfo? health;
  final String? error;

  @override
  List<Object?> get props => [platform, usage, loaded, health, error];
}

/// Datos de la portada: familia de hardware, modelo cargado y ahorro acumulado.
class OverviewCubit extends Cubit<OverviewState> {
  OverviewCubit(this._api) : super(const OverviewState());

  final MagnusApi _api;

  Future<void> load() async {
    try {
      final results = await Future.wait([
        _api.platform(),
        _api.usage(),
        _api.loadedModels(),
        _api.health(),
      ]);
      emit(OverviewState(
        platform: results[0] as PlatformInfo,
        usage: results[1] as UsageSummary,
        loaded: results[2] as List<LoadedModel>,
        health: results[3] as HealthInfo,
      ));
    } on Failure catch (f) {
      emit(OverviewState(error: f.message));
    }
  }
}
