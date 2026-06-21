import 'package:equatable/equatable.dart';

/// Error de dominio. Las capas data/domain lanzan estos; el BLoC los captura
/// y los convierte en estados de error para la UI.
sealed class Failure extends Equatable implements Exception {
  const Failure(this.message);
  final String message;

  @override
  List<Object?> get props => [message];

  @override
  String toString() => message;
}

/// No se pudo contactar al daemon (apagado, URL mala, red).
class ConnectionFailure extends Failure {
  const ConnectionFailure([super.message = 'No se pudo conectar al daemon de Magnus.']);
}

/// El daemon respondió con error (4xx/5xx).
class ServerFailure extends Failure {
  const ServerFailure(super.message);
}

/// Respuesta inesperada / parseo fallido.
class ParseFailure extends Failure {
  const ParseFailure([super.message = 'Respuesta inesperada del daemon.']);
}
