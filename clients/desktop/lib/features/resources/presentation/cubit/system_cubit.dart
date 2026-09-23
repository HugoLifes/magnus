import 'dart:async';

import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/error/failures.dart';
import '../../../../core/network/api_models.dart';
import '../../../../core/network/magnus_api.dart';

class SystemState extends Equatable {
  const SystemState({this.platform, this.sample, this.health, this.history = const [], this.error});

  final PlatformInfo? platform;
  final SystemSample? sample;
  final HealthInfo? health;

  /// Últimas lecturas de potencia (W), para la gráfica.
  final List<double> history;
  final String? error;

  SystemState copyWith({
    PlatformInfo? platform,
    SystemSample? sample,
    HealthInfo? health,
    List<double>? history,
    String? error,
  }) =>
      SystemState(
        platform: platform ?? this.platform,
        sample: sample ?? this.sample,
        health: health ?? this.health,
        history: history ?? this.history,
        error: error,
      );

  @override
  List<Object?> get props => [platform, sample, health, history, error];
}

/// Telemetría en vivo del host del daemon: consulta `/system` cada 2 s mientras
/// la página está abierta (el cubit se cierra al salir y deja de consultar).
class SystemCubit extends Cubit<SystemState> {
  SystemCubit(this._api) : super(const SystemState());

  final MagnusApi _api;
  Timer? _timer;
  static const _historyLength = 60;

  Future<void> start() async {
    try {
      final platform = await _api.platform();
      final health = await _api.health();
      emit(state.copyWith(platform: platform, health: health));
    } on Failure catch (f) {
      emit(state.copyWith(error: f.message));
    }
    await _tick();
    _timer = Timer.periodic(const Duration(seconds: 2), (_) => _tick());
  }

  Future<void> _tick() async {
    if (isClosed) return;
    try {
      final sample = await _api.system();
      final watts = sample.powerW;
      var history = state.history;
      if (watts != null) {
        history = [...history, watts];
        if (history.length > _historyLength) history = history.sublist(1);
      }
      if (!isClosed) emit(state.copyWith(sample: sample, history: history));
    } on Failure catch (f) {
      if (!isClosed) emit(state.copyWith(error: f.message));
    }
  }

  @override
  Future<void> close() {
    _timer?.cancel();
    return super.close();
  }
}
