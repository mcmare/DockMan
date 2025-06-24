Добавьте пользователя в группу docker (для Linux):
```bash
sudo usermod -aG docker $USER
newgrp docker
```

После этого перезапустите терминал или выполните newgrp docker, чтобы применить изменения.

Проверьте доступ:
```bash
docker ps
```

Убедитесь, что сокет /var/run/docker.sock доступен:
```bash
ls -l /var/run/docker.sock
```

Ожидаемый вывод:
```bash
srw-rw---- 1 root docker 0 Jun 24 11:57 /var/run/docker.sock
```

Если группа не docker или права неверные, исправьте:
```bash
sudo chown root:docker /var/run/docker.sock
sudo chmod 660 /var/run/docker.sock
```

