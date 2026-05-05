#!/bin/bash
# Script de gerenciamento do Celery para Léguas Franzinas
# Uso: ./celery-manager.sh [start|stop|restart|status|logs]

# Configurações
PROJECT_DIR="/home/user/app.leguasfranzinas.pt/app.leguasfranzinas.pt"
VENV_DIR="/home/user/venv"
CELERY_APP="my_project"
LOG_DIR="/var/log/celery"

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funções
print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Léguas Franzinas - Celery Manager${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

check_supervisor() {
    if ! command -v supervisorctl &> /dev/null; then
        print_error "Supervisor não está instalado!"
        exit 1
    fi
}

start_celery() {
    print_header
    print_info "Iniciando Celery..."
    
    check_supervisor
    
    sudo supervisorctl start leguas-celery:*
    
    if [ $? -eq 0 ]; then
        print_success "Celery iniciado com sucesso!"
        echo ""
        status_celery
    else
        print_error "Erro ao iniciar Celery"
        exit 1
    fi
}

stop_celery() {
    print_header
    print_info "Parando Celery..."
    
    check_supervisor
    
    sudo supervisorctl stop leguas-celery:*
    
    if [ $? -eq 0 ]; then
        print_success "Celery parado com sucesso!"
    else
        print_error "Erro ao parar Celery"
        exit 1
    fi
}

restart_celery() {
    print_header
    print_info "Reiniciando Celery..."
    
    check_supervisor
    
    sudo supervisorctl restart leguas-celery:*
    
    if [ $? -eq 0 ]; then
        print_success "Celery reiniciado com sucesso!"
        echo ""
        status_celery
    else
        print_error "Erro ao reiniciar Celery"
        exit 1
    fi
}

status_celery() {
    print_header
    print_info "Status do Celery:"
    echo ""
    
    check_supervisor
    
    sudo supervisorctl status leguas-celery:*
    
    echo ""
    print_info "Workers ativos:"
    cd $PROJECT_DIR
    source $VENV_DIR/bin/activate
    celery -A $CELERY_APP inspect active 2>/dev/null | grep -A 20 "active" || print_info "Nenhum worker ativo ou Celery não está respondendo"
    
    echo ""
    print_info "Tasks agendadas:"
    celery -A $CELERY_APP inspect scheduled 2>/dev/null | grep -A 20 "scheduled" || print_info "Nenhuma task agendada ou Celery não está respondendo"
}

view_logs() {
    print_header
    print_info "Visualizando logs do Celery..."
    echo ""
    
    PS3='Escolha qual log visualizar: '
    options=("Worker" "Beat" "Worker Errors" "Beat Errors" "Todos" "Voltar")
    select opt in "${options[@]}"
    do
        case $opt in
            "Worker")
                print_info "Visualizando worker.log (Ctrl+C para sair)..."
                sudo tail -f $LOG_DIR/worker.log
                break
                ;;
            "Beat")
                print_info "Visualizando beat.log (Ctrl+C para sair)..."
                sudo tail -f $LOG_DIR/beat.log
                break
                ;;
            "Worker Errors")
                print_info "Visualizando worker_error.log..."
                sudo tail -n 50 $LOG_DIR/worker_error.log
                break
                ;;
            "Beat Errors")
                print_info "Visualizando beat_error.log..."
                sudo tail -n 50 $LOG_DIR/beat_error.log
                break
                ;;
            "Todos")
                print_info "Últimas 30 linhas de cada log:"
                echo ""
                echo -e "${YELLOW}=== WORKER ===${NC}"
                sudo tail -n 30 $LOG_DIR/worker.log
                echo ""
                echo -e "${YELLOW}=== BEAT ===${NC}"
                sudo tail -n 30 $LOG_DIR/beat.log
                break
                ;;
            "Voltar")
                break
                ;;
            *) 
                print_error "Opção inválida"
                ;;
        esac
    done
}

test_celery() {
    print_header
    print_info "Testando Celery..."
    echo ""
    
    cd $PROJECT_DIR
    source $VENV_DIR/bin/activate
    
    print_info "Executando task de teste..."
    python manage.py shell -c "from core.tasks import test_task; result = test_task.delay(); print(f'Task ID: {result.id}')"
    
    if [ $? -eq 0 ]; then
        print_success "Task de teste enviada com sucesso!"
        print_info "Aguarde alguns segundos e verifique os logs"
    else
        print_error "Erro ao enviar task de teste"
    fi
}

purge_tasks() {
    print_header
    print_info "Limpando todas as tasks pendentes..."
    
    cd $PROJECT_DIR
    source $VENV_DIR/bin/activate
    
    read -p "Tem certeza que deseja remover TODAS as tasks pendentes? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]
    then
        celery -A $CELERY_APP purge -f
        print_success "Tasks pendentes removidas!"
    else
        print_info "Operação cancelada"
    fi
}

show_stats() {
    print_header
    print_info "Estatísticas do Celery:"
    echo ""
    
    cd $PROJECT_DIR
    source $VENV_DIR/bin/activate
    
    celery -A $CELERY_APP inspect stats
}

# Menu interativo
interactive_menu() {
    print_header
    echo ""
    PS3='Escolha uma opção: '
    options=("Start" "Stop" "Restart" "Status" "Logs" "Test Task" "Stats" "Purge Tasks" "Sair")
    select opt in "${options[@]}"
    do
        case $opt in
            "Start")
                start_celery
                ;;
            "Stop")
                stop_celery
                ;;
            "Restart")
                restart_celery
                ;;
            "Status")
                status_celery
                ;;
            "Logs")
                view_logs
                ;;
            "Test Task")
                test_celery
                ;;
            "Stats")
                show_stats
                ;;
            "Purge Tasks")
                purge_tasks
                ;;
            "Sair")
                print_info "Até logo!"
                exit 0
                ;;
            *) 
                print_error "Opção inválida"
                ;;
        esac
        echo ""
        read -p "Pressione Enter para continuar..."
        clear
        print_header
        echo ""
    done
}

# Main
case "$1" in
    start)
        start_celery
        ;;
    stop)
        stop_celery
        ;;
    restart)
        restart_celery
        ;;
    status)
        status_celery
        ;;
    logs)
        view_logs
        ;;
    test)
        test_celery
        ;;
    stats)
        show_stats
        ;;
    purge)
        purge_tasks
        ;;
    *)
        interactive_menu
        ;;
esac
